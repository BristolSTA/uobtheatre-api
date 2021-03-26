from uobtheatre.payments.square import PaymentProvider


def test_payment_provider(monkeypatch):
    pp = PaymentProvider()
    request_body: dict = {}

    class MockClient:
        class Payments:
            def create_payment(self, body):
                return body

        def __init__(self):
            self.payments = self.Payments()

    def mock_init(self):
        self.client = MockClient()

    monkeypatch.setattr(
        "uobtheatre.bookings.models.PaymentProvider.__init__", mock_init
    )

    pp.create_payment(10, "abc", "efg") == {
        "idempotency_key": "abc",
        "source_id": "efg",
        "amount_money": {"amount": 10, "currency": "GBP"},
    }
