import abc
import base64
import hmac
import json
import re
import uuid
from typing import TYPE_CHECKING, Optional, Type

from square.client import Client

from config.settings.common import BASE_URL, SQUARE_SETTINGS
from uobtheatre.payments import models as payment_models
from uobtheatre.utils.exceptions import (
    GQLExceptions,
    GQLFieldException,
    SquareException,
)
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
        self, value: int, pay_object: "Payable"
    ) -> Optional["payment_models.Payment"]:
        raise NotImplementedError

    @abc.abstractproperty
    def description(self):
        raise NotImplementedError

    @classmethod
    def create_payment_object(cls, pay_object: "Payable", value: int, **kwargs):
        return payment_models.Payment.objects.create(
            provider=cls.name,
            type=payment_models.Payment.PaymentType.PURCHASE,
            pay_object=pay_object,
            value=value,
            **kwargs,
        )


class Cash(PaymentMethod):
    description = "Manual cash payment"

    def pay(self, value: int, pay_object: "Payable") -> "payment_models.Payment":
        return self.create_payment_object(pay_object, value)


class Card(PaymentMethod):
    description = "Manual card payment"

    def pay(self, value: int, pay_object: "Payable") -> "payment_models.Payment":
        return self.create_payment_object(pay_object, value)


class SquarePOS(PaymentMethod):
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
    client = Client(
        square_version="2020-11-18",
        access_token=SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],
        environment=SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],
    )
    webhook_signature_key = SQUARE_SETTINGS["SQUARE_WEBHOOK_SIGNATURE_KEY"]
    webhook_url = f"{BASE_URL}/{SQUARE_SETTINGS['PATH']}"

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        super().__init__()

    def pay(self, value: int, pay_object: "Payable") -> None:
        """Send payment to point of sale device.

        Parameters:
            value (int): Amount of money being payed
            pay_object (Payable): The object being payed for

        Raises:
            SquareException: If the request was unsuccessful.
        """
        body = {
            "idempotency_key": str(uuid.uuid4()),
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

    @classmethod
    def handle_webhook(cls, data: dict, signature: str):
        """Handle checkout event for terminal api.

        Args:
            data (dict): The data provided in the webhook event
            signature (str): The signature of the requeset

        Raises:
            ValueError: If the signature is invalid
        """
        if not cls.is_valid_callback(data, signature):
            raise ValueError("Invalid signature")

        if data["type"] == "terminal.checkout.updated":
            cls.handle_terminal_checkout_updated_webhook(data["data"])

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
            cls.create_payment_object(
                booking,
                checkout["amount_money"]["amount"],
                provider_payment_id=checkout["payment_ids"][0],
                currency=checkout["amount_money"]["currency"],
            )
            booking.complete()

    @classmethod
    def list_devices(cls) -> list[dict]:
        """List the device codes available on square.

        Returns:
            list of dict: A list of dictionaries which store the device code
                info. When connection to a device the `device_id` should be
                used.

        Raises:
            SquareException: If the square request returns an error
        """
        response = cls.client.devices.list_device_codes()
        if not response.is_success():
            raise SquareException(response)
        return response.body["device_codes"]

    # TODO: Use or remove
    # @classmethod
    # def create_device_code(cls, name: str) -> str:
    #     """
    #     Create device code with square api with a given device name. This code
    #     can be used to connect the device to the api.

    #     Args:
    #         name (str): The name to assign the device code

    #     Returns:
    #         code (str): The device code used to connect
    #     """
    #     body = {
    #         "idempotency_key": str(uuid.uuid4()),
    #         "device_code": {
    #             "name": name,
    #             "product_type": "TERMINAL_API",
    #             "location_id": SQUARE_SETTINGS["SQUARE_LOCATION"],
    #         },
    #     }
    #     response = cls.client.devices.create_device_code(body)
    #     if response.errors:
    #         print(response.body["errors"])
    #     return response.body["device_code"]["code"]

    @classmethod
    def is_valid_callback(cls, callback_body: dict, callback_signature: str) -> bool:
        """
        When square sends a webhook to the api, it is import to check the
        webhook is actually from square. This uses the provided square webhook
        secret to validate this requeset is from them.

        The secret is provided by the "SQUARE_WEBHOOK_SIGNATURE_KEY"
        environment varaible.

        Args:
            callback_body (dict): The body of the webhook
            callback_signature (str): The provided signature

        Returns:
            bool: True if the signature is valid and therefore the message is
                from square
        """

        # Combine your webhook notification URL and the JSON body of the
        # incoming request into a single string
        clean_request = json.dumps(callback_body, separators=(",", ":"))
        url_request_bytes = cls.webhook_url.encode("utf-8") + clean_request.encode(
            "utf-8"
        )

        print(
            f"CHECKING: {cls.webhook_url}, {cls.webhook_signature_key}, {callback_signature}"
        )

        # Generate the HMAC-SHA1 signature of the string, signed with the
        # webhook signature key
        hmac_code = hmac.new(
            key=cls.webhook_signature_key.encode("utf-8"),
            msg=None,
            digestmod="sha1",
        )
        hmac_code.update(url_request_bytes)
        generated_hash = hmac_code.digest()

        # Compare the generated signature with the signature included in the
        # request
        return hmac.compare_digest(
            base64.b64encode(generated_hash), callback_signature.encode("utf-8")
        )


class SquareOnline(PaymentMethod):
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
    client = Client(
        square_version="2020-11-18",
        access_token=SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],
        environment=SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],
    )

    def __init__(self, nonce: str, idempotency_key: str) -> None:
        """
        Args:
            idempotency_key (string): This value is as unique indicator of
                the payment request and is used to ensure a payment can only be
                made once. I.e. if another payment is made with the same key
                the previous payment will be returned.
            nonce (string): The nonce is a reference to the completed payment
                form on the front-end. This allows square to determine the
                payment details to use.
        """
        self.nonce = nonce
        self.idempotency_key = idempotency_key
        super().__init__()

    def pay(self, value: int, pay_object: "Payable") -> "payment_models.Payment":
        """Make a payment using Square

        This makes a request to square to make a payment.

        Args:
            value (int): The value of the payment in pennies
            pay_object (Payable): The object being payed for

        Returns:
            ApiResponse: Response object from Square

        Raises:
            SquareException: If the request was unsuccessful.
        """
        body = {
            "idempotency_key": self.idempotency_key,
            "source_id": self.nonce,
            "amount_money": {"amount": value, "currency": "GBP"},
            "reference_id": pay_object.payment_reference_id,
        }
        response = self.client.payments.create_payment(body)

        if not response.is_success():
            raise SquareException(response)

        card_details = response.body["payment"]["card_details"]["card"]
        amount_details = response.body["payment"]["amount_money"]

        return self.create_payment_object(
            pay_object,
            amount_details["amount"],
            card_brand=card_details["card_brand"],
            last_4=card_details["last_4"],
            provider_payment_id=response.body["payment"]["id"],
            currency=amount_details["currency"],
        )
