import abc
import hmac
import json
import uuid
from typing import TYPE_CHECKING, Optional, Type

from square.client import Client

from config.settings.common import BASE_URL, SQUARE_SETTINGS
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

    def __init_subclass__(cls) -> None:
        cls.__all__.append(cls)

    @classproperty
    def choices(cls):  # pylint: disable=no-self-argument
        return [
            (method.__name__.upper(), method.__name__.upper()) for method in cls.__all__
        ]

    # TODO decide whether to use this pattern
    # @classmethod
    # def factory(cls, method_name: str, args: dict) -> "PaymentMethod":
    #     payment_method = next(
    #         method for method in cls.__all__ if method.name == method_name
    #     )
    #     init_args = payment_method.__init__.__code__.co_varnames
    #     func_args = {arg: args.get(arg) for arg in init_args}
    #     return payment_method(**func_args)

    @property
    def name(self):
        return self.__class__.__name__

    @abc.abstractmethod
    def pay(
        self, value: int, pay_object: "Payable"
    ) -> Optional["payment_models.Payment"]:
        pass

    @classmethod
    def create_payment_object(cls, pay_object: "Payable", value: int, **kwargs):
        return payment_models.Payment.objects.create(
            provider=cls.__name__,
            type=payment_models.Payment.PaymentType.PURCHASE,
            pay_object=pay_object,
            value=value,
            **kwargs,
        )


class Cash(PaymentMethod):
    def pay(self, value: int, pay_object: "Payable") -> "payment_models.Payment":
        return self.create_payment_object(pay_object, value)


class Card(PaymentMethod):
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

    client = Client(
        square_version="2020-11-18",
        access_token=SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],
        environment=SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],
    )

    def __init__(self, device_id: int) -> None:
        self.device_id = device_id
        super().__init__()

    def pay(self, value: int, pay_object: "Payable") -> None:
        """
        Send payment to point of sale device.

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
        if not response.is_sucess():
            raise SquareException(response)

    @classmethod
    def handle_checkout_event(cls, event_data: dict, pay_object: "Payable"):
        """
        Handle checkout event for terminal api.

        Args:
            event_data (dict): The data provided in the webhook event
            pay_object (Payable): The object the event is related to

        Returns:
            Payment: The payment if created (optional)
        """
        # TODO: Check payment is completed
        if event_data["type"] == "checkout.event":
            checkout = event_data["object"]["checkout"]
            return cls.create_payment_object(
                pay_object,
                checkout["amount_money"]["amount"],
                provider_payment_id=checkout["payment_ids"][0],
                currency=checkout["amount_money"]["currency"],
            )
        return None

    @classmethod
    def list_devices(cls) -> list[dict]:
        """
        List the device codes available on square.

        Returns:
            list of dict: A list of dictionaries which store the device code
                info. When connection to a device the `device_id` should be
                used.
        """
        response = cls.client.devices.list_device_codes()
        return response.body["device_codes"]

    @classmethod
    def create_device_code(cls, name: str) -> str:
        """
        Create device code with square api with a given device name. This code
        can be used to connect the device to the api.

        Args:
            name (str): The name to assign the device code

        Returns:
            code (str): The device code used to connect
        """
        body = {
            "idempotency_key": str(uuid.uuid4()),
            "device_code": {
                "name": name,
                "product_type": "TERMINAL_API",
                "location_id": SQUARE_SETTINGS["SQUARE_LOCATION"],
            },
        }
        response = cls.client.devices.create_device_code(body)
        if response.errors:
            print(response.body["errors"])
        return response.body["device_code"]["code"]

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

        # Combine your webhook notification URL and the JSON body of the incoming request into a single string
        square_path = f"{BASE_URL}/{SQUARE_SETTINGS['PATH']}"
        string_to_sign = (square_path + json.dumps(callback_body)).encode("utf-8")

        # Generate the HMAC-SHA1 signature of the string, signed with your webhook signature key
        string_signature = (
            hmac.new(
                key=SQUARE_SETTINGS["SQUARE_WEBHOOK_SIGNATURE_KEY"].encode("utf-8"),
                msg=string_to_sign,
                digestmod="sha1",
            )
            .digest()
            .encode("base64")
        )

        # Remove the trailing newline from the generated signature (this is a quirk of the Python library)
        string_signature = string_signature.rstrip("\n")

        # Compare your generated signature with the signature included in the request
        return hmac.compare_digest(string_signature, callback_signature)


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


def payment_method_is(payment_provider: str, payment_method: Type[PaymentMethod]):
    return payment_provider.lower() == payment_method.__name__.lower()
