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

    """
    Payments
    """

    def list_payments(self):
        return self.client.payments.list_payments()

    def create_payment(self):
        body = {
            "idempotency_key": str(uuid.uuid4()),
            "source_id": "cnon:card-nonce-ok",
            "amount_money": {"amount": 200, "currency": "GBP"},
        }
        return self.client.payments.create_payment(body)

    """
    Customers
    """

    def create_customer(self):
        body = {
            "given_name": "James",
        }
        return self.client.customers.create_customer(body)

    def create_customer_card(self, customer_id):
        body = {
            "card_nonse": "cnon:card-nonce-ok",
            "billing_address": {
                "address_line_1": "500 Electric Ave",
                "address_line_2": "Suite 600",
                "administrative_district_level_1": "NY",
                "country": "US",
                "locality": "New York",
                "postal_code": "10003",
            },
            "cardholder_name": "Amelia Earhart",
        }
        return self.client.customers.create_customer(customer_id, body)
