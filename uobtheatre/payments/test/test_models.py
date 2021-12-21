from unittest.mock import patch

import pytest

from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import Cash, SquareOnline, SquarePOS
from uobtheatre.payments.test.factories import PaymentFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value, result",
    [
        (100, "1.00 GBP"),
        (150, "1.50 GBP"),
        (199, "1.99 GBP"),
        (100.1, "1.00 GBP"),
    ],
)
def test_value_currency(value, result):
    payment = PaymentFactory(value=value, currency="GBP")
    assert payment.value_currency == result


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
    payment = PaymentFactory(provider_fee=0, provider_payment_id="abc")
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
        payment.sync_payment_with_provider()

    payment.refresh_from_db()
    assert payment.provider_fee == 58


@pytest.mark.django_db
def test_update_payment_from_square_no_provider_id(mock_square):
    payment = PaymentFactory(provider_fee=0, provider_payment_id=None)
    with mock_square(
        SquareOnline.client.payments,
        "get_payment",
    ) as mock:
        payment.sync_payment_with_provider()

    mock.assert_not_called()
    assert payment.provider_fee == 0


@pytest.mark.django_db
def test_update_payment_from_square_no_processing_fee(mock_square):
    payment = PaymentFactory(provider_fee=None, provider_payment_id="abc")
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
                "total_money": {"amount": 1990, "currency": "GBP"},
                "approved_money": {"amount": 1990, "currency": "GBP"},
            }
        },
    ):
        payment.sync_payment_with_provider()

    payment.refresh_from_db()
    assert payment.provider_fee is None


@pytest.mark.django_db
def test_handle_update_payment_webhook_checkout(mock_square):
    payment = PaymentFactory(
        provider_fee=None, provider_payment_id="abc", provider=SquarePOS.name
    )

    with mock_square(
        SquarePOS.client.terminal,
        "get_terminal_checkout",
        success=True,
        status_code=200,
        body={
            "checkout": {
                "amount_money": {"amount": 100, "currency": "GBP"},
                "id": "abc",
                "payment_ids": [
                    "3fgpz1iUfuxTkK83AqcK9Akx068YY",
                    "3fgpz1iUfuxTkK83AqcK9Akx068YZ",
                ],
                "status": "COMPLETED",
            },
        },
    ) as get_termial_checkout_mock, mock_square(
        SquarePOS.client.payments,
        "get_payment",
        success=True,
        status_code=200,
        body={
            "payment": {
                "id": "3fgpz1iUfuxTkK83AqcK9Akx068YY",
                "status": "COMPLETED",
                "processing_fee": [
                    {
                        "amount_money": {"amount": 58, "currency": "GBP"},
                    }
                ],
                "total_money": {"amount": 1990, "currency": "GBP"},
                "approved_money": {"amount": 1990, "currency": "GBP"},
            }
        },
    ):
        Payment.handle_update_payment_webhook(
            {
                "type": "payment",
                "object": {
                    "payment": {
                        "id": "notabc",
                        "terminal_checkout_id": "abc",
                    }
                },
            },
        )

    get_termial_checkout_mock.assert_called_once_with("abc")
    payment.refresh_from_db()
    assert payment.provider_fee == 58 * 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "provider, status, is_cancelled",
    [
        (SquarePOS.name, Payment.PaymentStatus.PENDING, True),
        (SquareOnline.name, Payment.PaymentStatus.PENDING, False),
        (SquarePOS.name, Payment.PaymentStatus.COMPLETED, False),
    ],
)
def test_cancel(provider, status, is_cancelled, mock_square):
    payment = PaymentFactory(provider=provider, status=status)
    with mock_square(
        SquarePOS.client.terminal, "cancel_terminal_checkout", success=True
    ) as mock:
        payment.cancel()

    # If cancelled this should have been called
    if is_cancelled:
        mock.assert_called_once_with(payment.provider_payment_id)
    else:
        mock.assert_not_called()

    # If pending assert this payment is deleted
    is_pending = status == Payment.PaymentStatus.PENDING
    assert not Payment.objects.filter(id=payment.id).exists() == is_pending


@pytest.mark.parametrize(
    "provider_name, provider_class",
    [
        ("SQUARE_POS", SquarePOS),
        ("SQUARE_ONLINE", SquareOnline),
    ],
)
def test_provider_class(provider_name, provider_class):
    payment = Payment(provider=provider_name)
    assert payment.provider_class == provider_class


def test_provider_class_unknown():
    payment = Payment(provider="abc")
    with pytest.raises(StopIteration):
        payment.provider_class  # pylint: disable=pointless-statement


@pytest.mark.django_db
def test_sync_all_payments():
    with_payment_fee = PaymentFactory(provider=SquareOnline.name, provider_fee=10)
    different_provider = PaymentFactory(provider=Cash.name, provider_fee=None)

    to_update = PaymentFactory(provider=SquareOnline.name, provider_fee=None)

    with patch.object(SquareOnline, "get_processing_fee") as online_get, patch.object(
        Cash, "get_processing_fee"
    ) as cash_get:
        online_get.return_value = 20
        Payment.sync_payments()
        cash_get.assert_not_called()
        online_get.assert_called_once_with(to_update.provider_payment_id, data=None)

    with_payment_fee.refresh_from_db()
    different_provider.refresh_from_db()
    to_update.refresh_from_db()

    assert with_payment_fee.provider_fee == 10
    assert different_provider.provider_fee is None
    assert to_update.provider_fee == 20


@pytest.mark.django_db
def test_handle_update_refund_webhook():
    data = {"object": {"refund": {"id": "abc"}}}
    payment = PaymentFactory(provider_payment_id="abc", type=Payment.PaymentType.REFUND)
    with patch(
        "uobtheatre.payments.payment_methods.SquareRefund.update_refund",
        return_value=None,
    ) as update_mock:
        Payment.handle_update_refund_webhook("abc", {"id": "abc"})

    update_mock.assert_called_once_with(payment, {"id": "abc"})
