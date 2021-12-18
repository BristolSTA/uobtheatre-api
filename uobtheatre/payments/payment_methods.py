import abc
import re
from typing import TYPE_CHECKING, Optional, Type
from uuid import uuid4

from django.conf import settings
from square.client import Client

from uobtheatre.mail.composer import MailComposer
from uobtheatre.payments import models as payment_models
from uobtheatre.utils.exceptions import GQLException, SquareException
from uobtheatre.utils.utils import classproperty

if TYPE_CHECKING:
    from uobtheatre.payments.payables import Payable


class TransactionMethod(abc.ABC):
    name: str

    def __init_subclass__(cls) -> None:
        cls.name = TransactionMethod.generate_name(cls.__name__)

    @classmethod
    @property
    def __all__(cls) -> list["TransactionMethod"]:
        return PaymentMethod.__all__ + RefundMethod.__all__

    @property
    @abc.abstractmethod
    def description(self):
        raise NotImplementedError

    @classmethod
    @property
    def non_manual_methods(cls) -> list[Type["TransactionMethod"]]:
        return [method for method in cls.__all__ if not method.is_manual]

    @staticmethod
    def generate_name(name):
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
        name = name.replace("-", "_")
        return name.upper()

    @classproperty
    def choices(cls):  # pylint: disable=no-self-argument
        return [(method.name, method.name) for method in cls.__all__]

    @classmethod
    def create_payment_object(
        cls, pay_object: "Payable", value: int, app_fee, **kwargs
    ) -> "payment_models.Payment":
        return payment_models.Payment.objects.create(
            provider=cls.name,
            pay_object=pay_object,
            value=value,
            app_fee=app_fee,
            **kwargs,
        )

    @classmethod
    @property
    def is_manual(cls):
        return issubclass(cls, ManualPaymentMethodMixin)

    @classmethod
    @property
    def is_refundable(cls):
        return issubclass(cls, Refundable)


class PaymentMethod(TransactionMethod, abc.ABC):
    """
    Abstract class for all payment methods.

    Every payment method should define a `pay` method. This will take a value
    and the the object being payed for and return (and save) a payment object
    if the payment is completed.

    Whenever a payment method is created it is automatically added to the
    __all__ attirbute of PaymentMethod. This will therefore add it to the
    choices field and the graphene enum.
    """

    __all__: list[Type["PaymentMethod"]] = []

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.__all__.append(cls)

    @abc.abstractmethod
    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Payment":
        raise NotImplementedError

    @classmethod
    def cancel(
        cls, payment: "payment_models.Payment"  # pylint: disable=unused-argument
    ):
        """Cancel the payment

        Most payment methods cannot be cancelled (as they will never be
        pending) so the default implementation is just to return.
        """
        return

    @classmethod
    @abc.abstractmethod
    def get_processing_fee(cls, payment_id: str, data: dict = None) -> Optional[int]:
        raise NotImplementedError

    @classmethod
    def create_payment_object(
        cls, pay_object: "Payable", value: int, app_fee, **kwargs
    ) -> "payment_models.Payment":
        payment = super().create_payment_object(pay_object, value, app_fee, **kwargs)
        payment.type == payment_models.Payment.PaymentType.PURCHASE
        return payment


class RefundMethod(TransactionMethod, abc.ABC):
    __all__: list[Type["RefundMethod"]] = []

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.__all__.append(cls)

    @abc.abstractmethod
    def refund(self, payment: "payment_models.Payment"):
        pass

    @staticmethod
    @abc.abstractmethod
    def update_refund(payment: "payment_models.Payment", data: dict):
        pass

    @classmethod
    def notify_refund_subject(payment: "payment_models.Payment"):
        user = payment.pay_object.user
        mail = (
            MailComposer()
            .line(
                f"Your payment of {payment.value_currency} has been successfully refunded (ID: {payment.provider_payment_id | payment.id})."
            )
            .line(
                f"This will have been refunded in your original payment method ({payment.provider_class.description}{f' {payment.card_brand} ending {payment.last_4}' if payment.card_brand and payment.last_4 else ''})"
            )
        )
        mail.send("Refund successfully processed", user.email)

    @classmethod
    def create_payment_object(
        cls, pay_object: "Payable", value: int, app_fee, **kwargs
    ) -> "payment_models.Payment":
        payment = super().create_payment_object(pay_object, value, app_fee, **kwargs)
        payment.type == payment_models.Payment.PaymentType.REFUND
        return payment


class Refundable(abc.ABC):
    @property
    @abc.abstractmethod
    def refund_method(self):
        pass


class SquarePaymentMethodMixin(abc.ABC):
    """
    Mixin for SquarePayment method classes which adds client and helper
    function. Sub-classes should import this mixin and the main PaymentMethod
    class.
    """

    client = Client(
        square_version="2020-11-18",
        access_token=settings.SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],  # type: ignore
        environment=settings.SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],  # type: ignore
    )

    @classmethod
    def get_payment(cls, payment_id: str):
        """Get full payment info from square for a given payment id.

        Args:
            payment_id (str): The id of the payment to be fetched

        Returns:
            dict: Payment response from square

        Raises:
            SquareException: When response is not successful
        """
        response = cls.client.payments.get_payment(payment_id)

        if not response.is_success():
            raise SquareException(response)

        return response.body["payment"]

    @classmethod
    def payment_processing_fee(cls, square_payment: dict) -> Optional[int]:
        """
        Get processing fee from a square payment dict.

        Args:
            square_payment (dict): Square object from square.

        Returns:
            int: Processing fee for payment
        """
        # If the processing fee has not be added to the payment
        if "processing_fee" not in square_payment:
            return None

        return sum(
            fee["amount_money"]["amount"] for fee in square_payment["processing_fee"]
        )


class ManualPaymentMethodMixin(abc.ABC):
    """
    Mixin for any manual payment method (one with no regiestered
    provider)
    """

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Payment":
        return self.create_payment_object(pay_object, value, app_fee)  # type: ignore # pylint: disable=arguments-differ

    @classmethod
    def get_processing_fee(cls, _, __=None) -> Optional[int]:
        return None


class Cash(ManualPaymentMethodMixin, PaymentMethod):
    """Manual cash payment method"""

    description = "Manual cash payment"


class Card(ManualPaymentMethodMixin, PaymentMethod):
    """Manual card payment method"""

    description = "Manual card payment"


class SquareRefund(RefundMethod):

    description = "Square refund"
    client = Client(
        square_version="2020-11-18",
        access_token=settings.SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],  # type: ignore
        environment=settings.SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],  # type: ignore
    )

    def __init__(self, idempotency_key: str):
        self.idempotency_key = idempotency_key

    def refund(self, payment: "payment_models.Payment"):
        if not payment.status == payment_models.Payment.PaymentStatus.PAID:
            raise GQLException(
                "You cannot refund a payment that has not been completed", code=400
            )

        body = {
            "idempotency_key": str(self.idempotency_key),
            "amount_money": {"amount": payment.value, "currency": payment.currency},
            "payment_id": payment.provider_payment_id,
        }
        response = self.client.refunds.refund_payment(body)

        if not response.is_success():
            raise SquareException(response)

        amount_details = response.body["refund"]["amount_money"]
        square_refund_id = response.body["refund"]["id"]

        self.create_payment_object(
            payment.pay_object,
            -amount_details["amount"],
            -payment.app_fee,
            type=payment_models.Payment.PaymentType.REFUND,
            provider_payment_id=square_refund_id,
            currency=amount_details["currency"],
            status=payment_models.Payment.PaymentStatus.PENDING,
        )

    @classmethod
    def update_refund(cls, payment: "payment_models.Payment", refund_data: dict):
        if processing_fees := refund_data.get("processing_fee"):
            payment.provider_fee = sum(
                fee["amount_money"]["amount"] for fee in processing_fees
            )
        if (
            refund_data["status"] == "COMPLETED"
            and not payment.status == payment_models.Payment.PaymentStatus.COMPLETED
        ):
            payment.status = payment_models.Payment.PaymentStatus.COMPLETED
            cls.notify_refund_subject(payment)
        payment.save()


class SquarePOS(PaymentMethod, SquarePaymentMethodMixin):
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
    ) -> "payment_models.Payment":
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
        if not response.is_success():
            raise SquareException(response)

        return self.create_payment_object(
            pay_object,
            value,
            app_fee,
            provider_payment_id=response.body["checkout"]["id"],
            currency="GBP",
            status=payment_models.Payment.PaymentStatus.PENDING,
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
            payment = payment_models.Payment.objects.get(
                provider_payment_id=checkout["id"]
            )

            payment.status = payment_models.Payment.PaymentStatus.COMPLETED
            payment.save()
            booking.complete()

        if checkout["status"] == "CANCELED":
            # Delete any payments that are linked to this checkout
            payment_models.Payment.objects.filter(
                provider_payment_id=checkout["id"],
                provider=SquarePOS.name,
                status=payment_models.Payment.PaymentStatus.PENDING,
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
        if not response.is_success():
            raise SquareException(response)
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

        if not response.is_success():
            raise SquareException(response)

        return response.body["checkout"]

    @classmethod
    def cancel(cls, payment: "payment_models.Payment") -> None:
        """Cancel terminal checkout.

        Args:
            payment (Payment): The payment to be canceled

        Raises:
            SquareException: When request is not successful
        """
        response = cls.client.terminal.cancel_terminal_checkout(
            payment.provider_payment_id
        )

        if not response.is_success():
            raise SquareException(response)

    @classmethod
    def get_processing_fee(  # pylint: disable=arguments-differ
        cls, checkout_id: str, data: dict = None
    ) -> Optional[int]:
        """
        Get processing fee for a square checkout.

        Args:
            checkout_id (str): The id of the square checkout
            data (dict, optional): Prefetched checkout reponse. This is used
                when the checkout has already been fetched from the api and the
                processing_fee is to be extracted from this response.

        Returns:
            int: The processing fee
        """
        checkout = data if data else cls.get_checkout(checkout_id)
        processing_fees = [
            cls.payment_processing_fee(cls.get_payment(payment_id))
            for payment_id in checkout["payment_ids"]
        ]
        # Sum all non-none processing fess
        return sum(filter(None, processing_fees))


class SquareOnline(Refundable, PaymentMethod, SquarePaymentMethodMixin):
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
    def refund_method(cls):
        return SquareRefund(idempotency_key=str(uuid4()))

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
    ) -> "payment_models.Payment":
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

        if not response.is_success():
            raise SquareException(response)

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
            provider_payment_id=square_payment_id,
            currency=amount_details["currency"],
        )

    @classmethod
    def get_processing_fee(cls, payment_id: str, data: dict = None) -> Optional[int]:
        """
        Get processing fee for a square payment.

        Args:
            payment_id (str): The id of the square payment
            data (dict, optional): Prefetched payment reponse. This is used
                when the payment has already been fetched from the api and the
                processing_fee is to be extracted from this response.

        Returns:
            int: The processing fee
        """
        return cls.payment_processing_fee(data or cls.get_payment(payment_id))

    def refund(self, payment: "payment_models.Payment", idempotency_key: str):
        refunder = SquareRefund(idempotency_key=idempotency_key)
        refunder.refund(payment)
