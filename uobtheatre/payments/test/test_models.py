from unittest import mock
from unittest.mock import PropertyMock, patch

import pytest

from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payment_methods import (
    Cash,
    SquareOnline,
    SquarePOS,
    SquareRefund,
)
from uobtheatre.payments.test.factories import (
    TransactionFactory,
    mock_payment_method,
    mock_refund_method,
)
from uobtheatre.utils.exceptions import GQLException, PaymentException


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
    payment = TransactionFactory(value=value, currency="GBP")
    assert payment.value_currency == result


@pytest.mark.django_db
def test_payment_url():
    payment = TransactionFactory(provider=SquareOnline.name, provider_payment_id="abc")
    assert (
        payment.url() == "https://squareupsandbox.com/dashboard/sales/transactions/abc"
    )


@pytest.mark.django_db
def test_payment_url_none():
    payment = TransactionFactory(provider=Cash.__name__, provider_payment_id="abc")
    assert payment.url() is None


@pytest.mark.django_db
def test_update_payment_from_square(mock_square):
    payment = TransactionFactory(provider_fee=0, provider_payment_id="abc")
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
    payment = TransactionFactory(provider_fee=0, provider_payment_id=None)
    with mock_square(
        SquareOnline.client.payments,
        "get_payment",
    ) as mock_get, pytest.raises(PaymentException):
        payment.sync_payment_with_provider()
        mock_get.assert_not_called()

    assert payment.provider_fee == 0


@pytest.mark.django_db
def test_update_payment_from_square_no_processing_fee(mock_square):
    payment = TransactionFactory(provider_fee=None, provider_payment_id="abc")
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
    payment = TransactionFactory(
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
        Transaction.handle_update_payment_webhook(
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
        (SquarePOS.name, Transaction.PaymentStatus.PENDING, True),
        (SquareOnline.name, Transaction.PaymentStatus.PENDING, False),
        (SquarePOS.name, Transaction.PaymentStatus.COMPLETED, False),
    ],
)
def test_cancel(provider, status, is_cancelled, mock_square):
    payment = TransactionFactory(provider=provider, status=status)
    with mock_square(
        SquarePOS.client.terminal, "cancel_terminal_checkout", success=True
    ) as mock_cancel:
        payment.cancel()

        # If cancelled this should have been called
        if is_cancelled:
            mock_cancel.assert_called_once_with(payment.provider_payment_id)
        else:
            mock_cancel.assert_not_called()

    # If pending assert this payment is deleted
    is_pending = status == Transaction.PaymentStatus.PENDING
    assert not Transaction.objects.filter(id=payment.id).exists() == is_pending


@pytest.mark.parametrize(
    "provider_name, provider_class",
    [
        ("SQUARE_POS", SquarePOS),
        ("SQUARE_ONLINE", SquareOnline),
    ],
)
def test_provider_class(provider_name, provider_class):
    payment = Transaction(provider=provider_name)
    assert payment.provider_class == provider_class


def test_provider_class_unknown():
    payment = Transaction(provider="abc")
    with pytest.raises(StopIteration):
        payment.provider_class  # pylint: disable=pointless-statement


@pytest.mark.django_db
def test_sync_all_payments():
    TransactionFactory(provider=SquareOnline.name, provider_fee=10)
    TransactionFactory(provider=Cash.name, provider_fee=None)

    to_update = TransactionFactory(provider=SquareOnline.name, provider_fee=None)

    with patch.object(SquareOnline, "sync_transaction") as online_sync, patch.object(
        Cash, "sync_transaction"
    ) as cash_sync:
        Transaction.sync_payments()
        cash_sync.assert_not_called()  # Not called because no provider ID
        online_sync.assert_called_once_with(to_update, None)


@pytest.mark.django_db
def test_handle_update_refund_webhook():
    payment = TransactionFactory(
        provider_payment_id="abc",
        type=Transaction.PaymentType.REFUND,
        provider=SquareRefund.name,
    )
    with patch(
        "uobtheatre.payments.payment_methods.SquareRefund.sync_transaction",
        return_value=None,
    ) as update_mock:
        Transaction.handle_update_refund_webhook("abc", {"id": "abc"})

    update_mock.assert_called_once_with(payment, {"id": "abc"})


@pytest.mark.django_db
def test_refund_pending_payment():
    payment = TransactionFactory(status=Transaction.PaymentStatus.PENDING)
    with pytest.raises(GQLException) as exc:
        payment.refund()
        assert exc.message == "You cannot refund a pending payment"


@pytest.mark.django_db
def test_refund_unrefundable_payment():
    payment = TransactionFactory(status=Transaction.PaymentStatus.COMPLETED)
    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider_class",
        new_callable=PropertyMock,
    ) as p_mock:
        p_mock.return_value = mock_payment_method(is_refundable=False)
        with pytest.raises(GQLException) as exc:
            payment.refund()
            assert exc.message == "You cannot refund a payment that is not refundable"


@pytest.mark.django_db
def test_refund_payment_with_refund_method():
    payment = TransactionFactory(status=Transaction.PaymentStatus.COMPLETED)
    refund_method = mock_refund_method()
    other_refund_method = mock_refund_method()
    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider_class",
        new_callable=PropertyMock,
    ) as p_mock:
        p_mock.return_value = mock_payment_method(is_refundable=True)
        payment.refund(refund_method=other_refund_method)

        # Assert correct refund method is called
        refund_method.refund.assert_not_called()
        other_refund_method.refund.assert_called_once_with(payment)


@pytest.mark.django_db
def test_refund_payment_without_refund_method():
    payment = TransactionFactory(status=Transaction.PaymentStatus.COMPLETED)
    refund_method = mock_refund_method()
    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider_class",
        new_callable=PropertyMock,
    ) as p_mock:
        p_mock.return_value = mock_payment_method(
            is_refundable=True, refund_method=refund_method
        )
        payment.refund()
        refund_method.refund.assert_called_once_with(payment)
