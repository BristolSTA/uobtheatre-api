import pytest

from uobtheatre.payments.payment_methods import Cash, SquareOnline
from uobtheatre.payments.test.factories import PaymentFactory


@pytest.mark.django_db
def test_payment_url():
    payment = PaymentFactory(provider=SquareOnline.name, provider_payment_id="abc")
    assert (
        payment.url() == "https://squareupsandbox.com/dashboard/sales/transactions/abc"
    )


@pytest.mark.django_db
def test_payment_url_none():
    payment = PaymentFactory(provider=Cash.__name__, provider_payment_id="abc")
    assert payment.url() is None


@pytest.mark.django_db
def test_update_payment_from_square(mock_square):
    payment = PaymentFactory(provider_fee=0)
    with mock_square(
        SquareOnline.client.payments,
        "get_payment",
        status_code=200,
        success=True,
        body={
            "payment": {
                "id": "RGdfG3spBBfui4ZJy4HFFogUKjKZY",
                "amount_money": {"amount": 1990, "currency": "GBP"},
                "status": "COMPLETED",
                "delay_duration": "PT168H",
                "source_type": "CARD",
                "processing_fee": [
                    {
                        "effective_at": "2021-10-03T09:46:42.000Z",
                        "type": "INITIAL",
                        "amount_money": {"amount": 58, "currency": "GBP"},
                    }
                ],
                "total_money": {"amount": 1990, "currency": "GBP"},
                "approved_money": {"amount": 1990, "currency": "GBP"},
            }
        },
    ):
        payment.update_from_square()

    payment.refresh_from_db()
    assert payment.provider_fee == 58
