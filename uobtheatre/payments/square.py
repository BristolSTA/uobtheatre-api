from square.client import Client

from config.settings.common import SQUARE_SETTINGS


class PaymentProvider:
    def __init__(self):
        self.client = Client(
            square_version="2020-11-18",
            access_token=SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],
            environment=SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],
        )

    """
    Payments
    """

    @classmethod
    def create_payment(cls, value, idempotency_key, nonce):
        pp = cls()
        body = {
            "idempotency_key": idempotency_key,
            "source_id": nonce,
            "amount_money": {"amount": value, "currency": "GBP"},
        }
        return pp.client.payments.create_payment(body)
