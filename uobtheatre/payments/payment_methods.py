import abc
import re
from typing import TYPE_CHECKING, Optional, Type

from django.conf import settings
from square.client import Client

from uobtheatre.payments import models as payment_models
from uobtheatre.utils.exceptions import SquareException
from uobtheatre.utils.utils import classproperty

if TYPE_CHECKING:
    from uobtheatre.payments.payables import Payable


class PaymentMethod(abc.ABC):
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
    name: str

    def __init_subclass__(cls) -> None:
        cls.name = PaymentMethod.generate_name(cls.__name__)
        cls.__all__.append(cls)

    @staticmethod
    def generate_name(name):
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
        name = name.replace("-", "_")
        return name.upper()

    @classproperty
    def choices(cls):  # pylint: disable=no-self-argument
        return [(method.name, method.name) for method in cls.__all__]

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

    @property
    @abc.abstractmethod
    def description(self):
        raise NotImplementedError

    @classmethod
    def create_payment_object(
        cls, pay_object: "Payable", value: int, app_fee, **kwargs
    ):
        return payment_models.Payment.objects.create(
            provider=cls.name,
            type=payment_models.Payment.PaymentType.PURCHASE,
            pay_object=pay_object,
            value=value,
            app_fee=app_fee,
            **kwargs,
        )


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


class Cash(PaymentMethod):
    """Manual cash payment method"""

    description = "Manual cash payment"

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Payment":
        return self.create_payment_object(pay_object, value, app_fee)


class Card(PaymentMethod):
    """Manual card payment method"""

    description = "Manual card payment"

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Payment":
        return self.create_payment_object(pay_object, value, app_fee)


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
                provider_payment_id=checkout["id"], provider=SquarePOS.name
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
    def get_checkout_processing_fee(cls, checkout_id: str) -> Optional[int]:
        """
        Get processing fee for a square checkout.

        Args:
            checkout_id (str): The id of the square checkout

        Returns:
            int: The processing fee
        """
        checkout = cls.get_checkout(checkout_id)
        processing_fees = [
            cls.payment_processing_fee(cls.get_payment(payment_id))
            for payment_id in checkout["payment_ids"]
        ]
        # Sum all non-none processing fess
        return sum(filter(None, processing_fees))


class SquareOnline(PaymentMethod, SquarePaymentMethodMixin):
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
