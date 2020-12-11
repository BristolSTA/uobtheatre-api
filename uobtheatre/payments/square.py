from square.client import Client
from config.settings.common import SQUARE_SETTINGS
import uuid


class PaymentProvider:
    def __init__(self):
        self.client = Client(
            square_version="2020-11-18",
            access_token=SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],
            environment=SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],
        )

    def list_payments(self):
        return self.client.payments.list_payments()

    def create_payment(self):
        body = {
            "idempotency_key": str(uuid.uuid4()),
            "source_id": "cnon:card-nonce-ok",
            "amount_money": {"amount": 200, "currency": "GBP"},
        }
        return self.client.payments.create_payment(body)


def payment():
    pp = PaymentProvider()
    return pp.list_payments()
