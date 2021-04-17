from square.client import Client

from config.settings.common import SQUARE_SETTINGS


class PaymentProvider:
    """Wrapper for Square payment Client.

    Currently payments for the API are made through Square. This wraps the
    Square Client object to make payments more agnostic to the provider.

    In order for this to work the following environment variables must be set:
        - SQUARE_ACCESS_TOKEN
        - SQUARE_ENVIRONMENT
    For the sandbox values please ask the webmaster. Currently all tests that
    require these values are marked with `square_integration`.and can therefor
    be skipped if not required by adding
        `-m "not square_integration"`
    to the test command (`make test` or `make test-v`)
    """

    def __init__(self):
        self.client = Client(
            square_version="2020-11-18",
            access_token=SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],
            environment=SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],
        )

    @classmethod
    def create_payment(cls, value: int, idempotency_key: str, nonce: str):
        """Make a payment using Square

        This makes a request to square to make a payment.

        Args:
            value (int): The value of the payment in pennies.
            idempotency_key (string): This value is as unique indicator of
                the payment request and is used to ensure a payment can only be
                made once. I.e. if another payment is made with the same key
                the previous payment will be returned.
            nonce (string): The nonce is a reference to the completed payment
                form on the front-end. This allows square to determine the
                payment details to use.

        Returns:
            ApiResponse: Response object from Square
        """

        # TODO all future payments using the Booking reference will be rejected
        # atm. Could this not be bad
        payment_provider = cls()
        body = {
            "idempotency_key": idempotency_key,
            "source_id": nonce,
            "amount_money": {"amount": value, "currency": "GBP"},
        }
        return payment_provider.client.payments.create_payment(body)
