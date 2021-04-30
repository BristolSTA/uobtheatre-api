import pytest

from uobtheatre.payments.models import Payment
from uobtheatre.payments.test.factories import PaymentFactory


@pytest.mark.django_db
def test_payment_url():
    payment = PaymentFactory(
        provider=Payment.PaymentProvider.SQUARE_ONLINE, provider_payment_id="abc"
    )
    assert (
        payment.url() == "https://squareupsandbox.com/dashboard/sales/transactions/abc"
    )


@pytest.mark.django_db
def test_payment_url_none():
    payment = PaymentFactory(
        provider=Payment.PaymentProvider.CASH, provider_payment_id="abc"
    )
    assert payment.url() is None
