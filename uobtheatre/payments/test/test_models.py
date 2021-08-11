import pytest

from uobtheatre.payments.payment_methods import Cash, PaymentMethod, SquareOnline
from uobtheatre.payments.test.factories import PaymentFactory


@pytest.mark.django_db
def test_payment_url():
    payment = PaymentFactory(provider=SquareOnline.__name__, provider_payment_id="abc")
    assert (
        payment.url() == "https://squareupsandbox.com/dashboard/sales/transactions/abc"
    )


@pytest.mark.django_db
def test_payment_url_none():
    payment = PaymentFactory(provider=Cash.__name__, provider_payment_id="abc")
    assert payment.url() is None


def test_payment_method_all():
    assert [method.__name__ for method in PaymentMethod.__all__] == [
        "Cash",
        "Card",
        "SquarePOS",
        "SquareOnline",
    ]
