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


def test_create_device_code():
    payment_provider = PaymentProvider()
    code = payment_provider.create_device_code("Boxoffice1")
    print(code)


def test_list_device_code():
    payment_provider = PaymentProvider()
    print(payment_provider.list_devices())


def test_create_terminal_payment():
    payment_provider = PaymentProvider()
    response = payment_provider.create_terminal_payment(
        "9fa747a2-25ff-48ee-b078-04381f7c828f", 100, "abc"
    )
    print(response)
