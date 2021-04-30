from uobtheatre.payments.square import PaymentProvider  # pylint: disable=cyclic-import


def test_payment_provider(monkeypatch):
    """Test payment_provider class with mocked square"""
    payment_provider = PaymentProvider()

    class MockClient:
        """Mock square payment provider."""

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

    assert payment_provider.create_payment(10, "abc", "efg") == {
        "idempotency_key": "abc",
        "source_id": "efg",
        "amount_money": {"amount": 10, "currency": "GBP"},
    }
