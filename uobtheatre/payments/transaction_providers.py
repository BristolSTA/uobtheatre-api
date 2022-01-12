import abc
import re
from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Type
from uuid import uuid4

from django.conf import settings
from square.client import Client
from square.http.api_response import ApiResponse as SquareApiResponse

from uobtheatre.payments import models as payment_models
from uobtheatre.utils.exceptions import PaymentException, SquareException

if TYPE_CHECKING:
    from uobtheatre.payments.payables import Payable


class TransactionProvider(abc.ABC):
    """
    Absctact class for transactions methods. This includes both refunds and
    payments.
    """

    name: str

    def __init_subclass__(cls) -> None:
        cls.name = TransactionProvider.generate_name(cls.__name__)

    @classmethod
    @property
    def __all__(cls) -> Sequence[Type["TransactionProvider"]]:
        return PaymentProvider.__all__ + RefundProvider.__all__  # type: ignore

    @classmethod
    @property
    @abc.abstractmethod
    def description(cls):
        pass

    @classmethod
    @property
    def non_manual_methods(cls) -> list[Type["TransactionProvider"]]:
        return [method for method in cls.__all__ if not method.is_manual]  # type: ignore

    @staticmethod
    def generate_name(name):
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
        name = name.replace("-", "_")
        return name.upper()

    @classmethod
    @property
    def choices(cls):
        choices = [(method.name, method.name) for method in cls.__all__]
        return choices

    @classmethod
    def create_payment_object(
        cls, pay_object: "Payable", value: int, app_fee, **kwargs
    ) -> "payment_models.Transaction":
        return payment_models.Transaction.objects.create(
            provider_name=cls.name,
            pay_object=pay_object,
            value=value,
            app_fee=app_fee,
            **kwargs,
        )

    @classmethod
    def sync_transaction(cls, payment: "payment_models.Transaction", data: dict = None):
        """Syncs the refund payment from the provider"""

    @classmethod
    def cancel(
        cls, payment: "payment_models.Transaction"  # pylint: disable=unused-argument
    ):
        """Cancel the payment

        Most payment methods cannot be cancelled (as they will never be
        pending) so the default implementation is just to return.
        """
        return

    @classmethod
    @property
    def is_manual(cls) -> bool:
        """Whether this payment method is a manual payment method"""
        return issubclass(cls, ManualPaymentMethodMixin)

    @classmethod
    def get_payment_provider_id(cls, payment: "payment_models.Transaction") -> str:
        """Get the ID of the provided payment assigned by the provider"""
        if not payment.provider_transaction_id:
            raise PaymentException("Payment has no provider_transaction_id")
        return payment.provider_transaction_id


class PaymentProvider(TransactionProvider, abc.ABC):
    """
    Abstract class for all payment methods.

    Every payment method should define a `pay` method. This will take a value
    and the the object being payed for and return (and save) a payment object
    if the payment is completed.

    Whenever a payment method is created it is automatically added to the
    __all__ attirbute of PaymentMethod. This will therefore add it to the
    choices field and the graphene enum.
    """

    __all__: Sequence[Type["PaymentProvider"]] = []

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.__all__.append(cls)  # type: ignore

    @abc.abstractmethod
    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Transaction":
        raise NotImplementedError

    @classmethod
    def create_payment_object(
        cls, pay_object: "Payable", value: int, app_fee, **kwargs
    ) -> "payment_models.Transaction":
        payment = super().create_payment_object(
            pay_object,
            value,
            app_fee,
            type=payment_models.Transaction.Type.PAYMENT,
            **kwargs,
        )
        return payment

    @classmethod
    @property
    def is_refundable(cls) -> bool:
        return issubclass(cls, Refundable)

    @classmethod
    @property
    def refundable_payment_methods(cls) -> tuple[Type["Refundable"], ...]:
        return tuple(method for method in cls.__all__ if issubclass(method, Refundable))

    @classmethod
    @property
    def auto_refundable_providers(cls) -> tuple[Type["Refundable"], ...]:
        return tuple(
            method
            for method in cls.refundable_payment_methods  # type: ignore
            if issubclass(method, Refundable) and method.is_auto_refundable
        )


class RefundProvider(TransactionProvider, abc.ABC):
    """
    Abscract class for all refund methods.
    """

    __all__: Sequence[Type["RefundProvider"]] = []

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.__all__ = cls.__all__.append(cls)  # type: ignore

    @classmethod
    @property
    @abc.abstractmethod
    def is_automatic(cls) -> bool:
        """
        This determines wether the refund method can be used without any
        interaction from the uob team.
        """

    @classmethod
    def create_payment_object(
        cls, pay_object: "Payable", value: int, app_fee, **kwargs
    ) -> "payment_models.Transaction":
        payment = super().create_payment_object(
            pay_object,
            value,
            app_fee,
            type=payment_models.Transaction.Type.REFUND,
            **kwargs,
        )
        return payment


class Refundable(abc.ABC):
    """
    A mixin which can be added to a payment method. This makes the payment
    method refundable. A refundable payment method must have refund_methods.
    These are the methods that can be used to refund payments created with this
    payment method.
    """

    @classmethod
    @property
    @abc.abstractmethod
    def refund_providers(cls) -> tuple[RefundProvider]:
        """A tuple of methods that can be used to refund payments"""

    @classmethod
    def is_valid_refund_provider(cls, provider: RefundProvider) -> bool:
        return type(provider) in set(
            type(provider) for provider in cls.refund_providers  # type: ignore
        )

    @classmethod
    @property
    def automatic_refund_provider(cls) -> Optional[RefundProvider]:
        """
        Return the first payment method that can be used automatically. This
        means it can be used to refund the payment method without any
        interaction from the uob team.
        """
        return next(
            (method for method in cls.refund_providers if method.is_automatic), None  # type: ignore
        )

    @classmethod
    @property
    def is_auto_refundable(cls) -> bool:
        """
        Returns whether this payment method has an automatic refund method.
        """
        return cls.automatic_refund_provider is not None


class SquareAPIMixin(abc.ABC):
    """Mixin that inserts square API client and handlers"""

    client = Client(
        square_version="2020-11-18",
        access_token=settings.SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],  # type: ignore
        environment=settings.SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],  # type: ignore
    )

    @classmethod
    def _handle_response_failure(cls, response: SquareApiResponse) -> None:
        if not response.is_success():
            raise SquareException(response)

    @classmethod
    def _square_transaction_processing_fee(cls, square_object: dict) -> Optional[int]:
        """
        Get processing fee from a square transaction object dict.

        Args:
            square_object (dict): Square object from square.

        Returns:
            int: Processing fee for payment
        """
        # If the processing fee has not be added to the payment
        if "processing_fee" not in square_object:
            return None

        return sum(
            fee["amount_money"]["amount"] for fee in square_object["processing_fee"]
        )

    @classmethod
    def _fill_payment_from_square_response_object(cls, payment, response_object):
        """Updates and fills a payment model from a refund response object"""
        payment.status = payment_models.Transaction.Status.from_square_status(
            response_object["status"]
        )
        if processing_fees := cls._square_transaction_processing_fee(response_object):
            payment.provider_fee = processing_fees
        return payment


class SquarePaymentMethod(SquareAPIMixin, abc.ABC):
    """
    Mixin for SquarePayment method classes which adds client and helper
    function. Sub-classes should import this mixin and the main PaymentMethod
    class.
    """

    @classmethod
    def get_payment(cls, payment_id: str) -> Dict[Any, Any]:
        """Get full payment info from square for a given payment id.

        Args:
            payment_id (str): The id of the payment to be fetched

        Returns:
            dict: Payment response from square

        Raises:
            SquareException: When response is not successful
        """
        response = cls.client.payments.get_payment(payment_id)
        cls._handle_response_failure(response)  # pylint: disable=no-member

        return response.body["payment"]


class ManualRefund(RefundProvider):
    """
    Refund method for refunding square payments.
    """

    description = "Manually refund"
    is_automatic = False

    def refund(self, payment: "payment_models.Transaction"):
        self.create_payment_object(
            payment.pay_object,
            -payment.value,
            -payment.app_fee if payment.app_fee is not None else None,
            provider_fee=-payment.provider_fee if payment.provider_fee else None,
            status=payment_models.Transaction.Status.COMPLETED,
        )


class SquareRefund(RefundProvider, SquareAPIMixin):
    """
    Refund method for refunding square payments.
    """

    description = "Square refund"
    is_automatic = True

    def __init__(self, idempotency_key: str):
        self.idempotency_key = idempotency_key

    def refund(self, payment: "payment_models.Transaction"):
        """
        Refund payment using square refund api
        """
        body = {
            "idempotency_key": str(self.idempotency_key),
            "amount_money": {"amount": payment.value, "currency": payment.currency},
            "payment_id": payment.provider_transaction_id,
        }
        response = self.client.refunds.refund_payment(body)
        self._handle_response_failure(response)

        amount_details = response.body["refund"]["amount_money"]
        square_refund_id = response.body["refund"]["id"]

        self.create_payment_object(
            payment.pay_object,
            -amount_details["amount"],
            -payment.app_fee if payment.app_fee is not None else None,
            provider_transaction_id=square_refund_id,
            currency=amount_details["currency"],
            status=payment_models.Transaction.Status.PENDING,
        )

    @classmethod
    def sync_transaction(cls, payment: "payment_models.Transaction", data: dict = None):
        if not data:
            response = cls.client.refunds.get_payment_refund(
                cls.get_payment_provider_id(payment)
            )
            cls._handle_response_failure(response)
            data = response.body["refund"]

        cls._fill_payment_from_square_response_object(payment, data).save()


class ManualPaymentMethodMixin(Refundable, abc.ABC):
    """
    Mixin for any manual payment method (one with no regiestered
    provider)
    """

    @classmethod
    @property
    def refund_providers(cls):
        return (ManualRefund(),)

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Transaction":
        return self.create_payment_object(pay_object, value, app_fee)  # type: ignore # pylint: disable=arguments-differ

    @classmethod
    def sync_transaction(cls, *_, **__):
        return


class Cash(ManualPaymentMethodMixin, PaymentProvider):
    """Manual cash payment method"""

    description = "Manual cash payment"


class Card(ManualPaymentMethodMixin, PaymentProvider):
    """Manual card payment method"""

    description = "Manual card payment"


class SquarePOS(PaymentProvider, SquarePaymentMethod):
    """
    Uses Square terminal api to create payment. Used for inperson card
    transactions.

    In order for this to work the following environment variables must be set:
        - SQUARE_ACCESS_TOKEN
        - SQUARE_ENVIRONMENT
    For the sandbox values please ask the webmaster. Currently all tests that
    require these values are marked with `square_integration`.and can therefor
    be skipped if not required by adding `-m "not square_integration"` to the
    test command (`make test` or `make test-v`)
    """

    description = "Square terminal card payment"

    def __init__(self, device_id: str, idempotency_key: str) -> None:
        self.device_id = device_id
        self.idempotency_key = idempotency_key
        super().__init__()

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Transaction":
        """Send payment to point of sale device.

        Args:
            value (int): Amount of money being payed
            app_fee (int): The amount we charge for the payment.
            pay_object (Payable): The object being payed for

        Raises:
            SquareException: If the request was unsuccessful.

        Returns:
            Payment: Created payment
        """
        body = {
            "idempotency_key": self.idempotency_key,
            "checkout": {
                "amount_money": {
                    "amount": value,
                    "currency": "GBP",
                },
                "reference_id": pay_object.payment_reference_id,
                "device_options": {
                    "device_id": self.device_id,
                },
            },
        }
        response = self.client.terminal.create_terminal_checkout(body)
        self._handle_response_failure(response)

        return self.create_payment_object(
            pay_object,
            value,
            app_fee,
            provider_transaction_id=response.body["checkout"]["id"],
            currency="GBP",
            status=payment_models.Transaction.Status.PENDING,
        )

    @classmethod
    def handle_terminal_checkout_updated_webhook(cls, data: dict):
        """Handle a terminal checkout update event

        Function to handle a square webhook containing terminal checkout
        udpate. If the status of the checkout is completed the booking can be
        completed and a payment object can be created.
        """

        from uobtheatre.bookings.models import Booking

        checkout = data["object"]["checkout"]
        booking = Booking.objects.get(reference=checkout["reference_id"])

        if checkout["status"] == "COMPLETED":
            payment = payment_models.Transaction.objects.get(
                provider_transaction_id=checkout["id"]
            )

            payment.status = payment_models.Transaction.Status.COMPLETED
            payment.save()
            booking.complete(payment)

        if checkout["status"] == "CANCELED":
            # Delete any payments that are linked to this checkout
            payment_models.Transaction.objects.filter(
                provider_transaction_id=checkout["id"],
                provider_name=SquarePOS.name,
                status=payment_models.Transaction.Status.PENDING,
            ).delete()

    @classmethod
    def list_devices(cls, product_type: str = None, status: str = None) -> list[dict]:
        """List the device codes available on square.

        Args:
            product_type (str): If provided filters the result by the device
                type, for square_terminal use: "TERMINAL_API"
            status (str): If provided filters the result by the status type,
                for just paried devices use: "PAIRED"

        Returns:
            list of dict: A list of dictionaries which store the device code
                info. When connection to a device the `device_id` should be
                used.

        Raises:
            SquareException: If the square request returns an error
        """
        response = cls.client.devices.list_device_codes(
            status=status, product_type=product_type
        )
        cls._handle_response_failure(response)

        return response.body.get("device_codes") or []

    @classmethod
    def get_checkout(cls, checkout_id: str):
        """Get checkout info from square for a given checkout id.

        Args:
            checkout_id (str): The id of the checkout to be fetched

        Returns:
            dict: Checkout response from square

        Raises:
            SquareException: When response is not successful
        """
        response = cls.client.terminal.get_terminal_checkout(checkout_id)
        cls._handle_response_failure(response)

        return response.body["checkout"]

    @classmethod
    def cancel(cls, payment: "payment_models.Transaction") -> None:
        """Cancel terminal checkout.

        Args:
            payment (Payment): The payment to be canceled

        Raises:
            SquareException: When request is not successful
        """
        response = cls.client.terminal.cancel_terminal_checkout(
            payment.provider_transaction_id
        )
        cls._handle_response_failure(response)

    @classmethod
    def sync_transaction(cls, payment: "payment_models.Transaction", data: dict = None):
        """Syncs the given payment with the raw payment data"""
        payment_id = cls.get_payment_provider_id(payment)

        checkout = data if data else cls.get_checkout(payment_id)
        payment.provider_fee = sum(
            filter(
                None,
                [
                    cls._square_transaction_processing_fee(cls.get_payment(payment_id))
                    for payment_id in checkout["payment_ids"]
                ],
            )
        )
        payment.status = payment_models.Transaction.Status.from_square_status(
            checkout["status"]
        )
        payment.save()


class SquareOnline(Refundable, PaymentProvider, SquarePaymentMethod):
    """
    Uses Square checkout api to create payment. Used for online transactions.

    In order for this to work the following environment variables must be set:
        - SQUARE_ACCESS_TOKEN
        - SQUARE_ENVIRONMENT
    For the sandbox values please ask the webmaster. Currently all tests that
    require these values are marked with `square_integration`.and can therefor
    be skipped if not required by adding `-m "not square_integration"` to the
    test command (`make test` or `make test-v`)
    """

    description = "Square online card payment"

    @classmethod
    @property
    def refund_providers(cls):
        return (SquareRefund(idempotency_key=str(uuid4())),)

    def __init__(self, nonce: str, idempotency_key: str) -> None:
        """
        Args:
            idempotency_key (str): This value is as unique indicator of
                the payment request and is used to ensure a payment can only be
                made once. I.e. if another payment is made with the same key
                the previous payment will be returned.
            nonce (str): The nonce is a reference to the completed payment
                form on the front-end. This allows square to determine the
                payment details to use.
        """
        self.nonce = nonce
        self.idempotency_key = idempotency_key
        super().__init__()

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Transaction":
        """Make a payment using Square

        This makes a request to square to make a payment.

        Args:
            value (int): The value of the payment in pennies
            app_fee (int): The amount we charge for the payment.
            pay_object (Payable): The object being payed for

        Returns:
            ApiResponse: Response object from Square

        Raises:
            SquareException: If the request was unsuccessful.
        """
        body = {
            "idempotency_key": str(self.idempotency_key),
            "source_id": self.nonce,
            "amount_money": {"amount": value, "currency": "GBP"},
            "reference_id": pay_object.payment_reference_id,
        }
        response = self.client.payments.create_payment(body)
        self._handle_response_failure(response)

        card_details = response.body["payment"]["card_details"]["card"]
        amount_details = response.body["payment"]["amount_money"]

        # Create payment object with info that is returned
        square_payment_id = response.body["payment"]["id"]
        return self.create_payment_object(
            pay_object,
            amount_details["amount"],
            app_fee,
            card_brand=card_details["card_brand"],
            last_4=card_details["last_4"],
            provider_transaction_id=square_payment_id,
            currency=amount_details["currency"],
        )

    @classmethod
    def sync_transaction(cls, payment: "payment_models.Transaction", data: dict = None):
        """Syncs the given payment with the raw payment data"""
        payment_id = cls.get_payment_provider_id(payment)

        if data is None:
            data = cls.get_payment(payment_id)
        cls._fill_payment_from_square_response_object(payment, data).save()
