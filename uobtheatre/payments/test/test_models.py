from unittest import mock
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from pytest_django.asserts import assertQuerysetEqual

from uobtheatre.payments.models import Transaction
from uobtheatre.payments.test.factories import (
    TransactionFactory,
    mock_payment_method,
    mock_refund_method,
)
from uobtheatre.payments.transaction_providers import (
    Cash,
    SquareOnline,
    SquarePOS,
    SquareRefund,
)
from uobtheatre.utils.exceptions import PaymentException


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
    payment = TransactionFactory(
        provider_name=SquareOnline.name, provider_transaction_id="abc"
    )
    assert (
        payment.url() == "https://squareupsandbox.com/dashboard/sales/transactions/abc"
    )


@pytest.mark.django_db
def test_payment_url_none():
    payment = TransactionFactory(
        provider_name=Cash.__name__, provider_transaction_id="abc"
    )
    assert payment.url() is None


@pytest.mark.django_db
def test_transaction_type_filters():
    payment_1 = TransactionFactory(type=Transaction.Type.PAYMENT)
    refund_1 = TransactionFactory(type=Transaction.Type.REFUND)

    assertQuerysetEqual(Transaction.objects.payments(), [payment_1])
    assertQuerysetEqual(Transaction.objects.refunds(), [refund_1])


@pytest.mark.django_db
def test_update_payment_from_square(mock_square):
    payment = TransactionFactory(provider_fee=0, provider_transaction_id="abc")
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
        payment.sync_transaction_with_provider()

    payment.refresh_from_db()
    assert payment.provider_fee == 58


@pytest.mark.django_db
def test_update_payment_from_square_no_provider_id(mock_square):
    payment = TransactionFactory(provider_fee=0, provider_transaction_id=None)
    with mock_square(
        SquareOnline.client.payments,
        "get_payment",
    ) as mock_get, pytest.raises(PaymentException):
        payment.sync_transaction_with_provider()
    mock_get.assert_not_called()

    assert payment.provider_fee == 0


@pytest.mark.django_db
def test_update_payment_from_square_no_processing_fee(mock_square):
    payment = TransactionFactory(provider_fee=None, provider_transaction_id="abc")
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
        payment.sync_transaction_with_provider()

    payment.refresh_from_db()
    assert payment.provider_fee is None


@pytest.mark.django_db
def test_handle_update_payment_webhook_checkout(mock_square):
    payment = TransactionFactory(
        provider_fee=None, provider_transaction_id="abc", provider_name=SquarePOS.name
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
        (SquarePOS.name, Transaction.Status.PENDING, True),
        (SquareOnline.name, Transaction.Status.PENDING, False),
        (SquarePOS.name, Transaction.Status.COMPLETED, False),
    ],
)
def test_cancel(provider, status, is_cancelled, mock_square):
    payment = TransactionFactory(provider_name=provider, status=status)
    with mock_square(
        SquarePOS.client.terminal, "cancel_terminal_checkout", success=True
    ) as mock_cancel:
        payment.cancel()

        # If cancelled this should have been called
        if is_cancelled:
            mock_cancel.assert_called_once_with(payment.provider_transaction_id)
        else:
            mock_cancel.assert_not_called()

    # If pending assert this payment is deleted
    is_pending = status == Transaction.Status.PENDING
    assert not Transaction.objects.filter(id=payment.id).exists() == is_pending


@pytest.mark.parametrize(
    "provider_name, provider_class",
    [
        ("SQUARE_POS", SquarePOS),
        ("SQUARE_ONLINE", SquareOnline),
    ],
)
def test_provider_class(provider_name, provider_class):
    payment = Transaction(provider_name=provider_name)
    assert payment.provider == provider_class


def test_provider_class_unknown():
    payment = Transaction(provider_name="abc")
    with pytest.raises(StopIteration):
        payment.provider  # pylint: disable=pointless-statement


@pytest.mark.django_db
def test_handle_update_refund_webhook():
    payment = TransactionFactory(
        provider_transaction_id="abc",
        type=Transaction.Type.REFUND,
        provider_name=SquareRefund.name,
    )
    with patch(
        "uobtheatre.payments.transaction_providers.SquareRefund.sync_transaction",
        return_value=None,
    ) as update_mock:
        Transaction.handle_update_refund_webhook("abc", {"id": "abc"})

    update_mock.assert_called_once_with(payment, {"id": "abc"})


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        Transaction.Status.PENDING,
        Transaction.Status.FAILED,
    ],
)
def test_cant_be_refunded_when_not_completed(status):
    transaction = TransactionFactory(status=status)

    assert transaction.can_be_refunded() is False
    with pytest.raises(PaymentException) as exception:
        transaction.can_be_refunded(raises=True)
    assert (
        exception.value.message == f"A {status.label.lower()} payment can't be refunded"
    )


@pytest.mark.django_db
def test_cant_be_refunded_when_invalid_refund_provider():
    transaction = TransactionFactory()
    payment_method = mock_payment_method(name="payment_provider_name")
    refund_provider = mock_refund_method(name="refund_provider_name")

    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider",
        new_callable=PropertyMock(return_value=payment_method),
    ):
        payment_method.is_valid_refund_provider = MagicMock(return_value=False)

        transaction.can_be_refunded(refund_provider) is False
        with pytest.raises(PaymentException) as exception:
            transaction.can_be_refunded(refund_provider, raises=True)
        assert (
            exception.value.message
            == "Cannot use refund provider refund_provider_name with a payment_provider_name payment"
        )
        payment_method.is_valid_refund_provider.assert_called_with(refund_provider)


@pytest.mark.django_db
def test_can_be_refunded_when_valid_refund_provider():
    transaction = TransactionFactory()
    payment_method = mock_payment_method(name="payment_provider_name")
    refund_provider = mock_refund_method(name="refund_provider_name")

    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider",
        new_callable=PropertyMock(return_value=payment_method),
    ):
        payment_method.is_valid_refund_provider = MagicMock(return_value=True)
        transaction.can_be_refunded(refund_provider, raises=True)
        payment_method.is_valid_refund_provider.assert_called_with(refund_provider)


@pytest.mark.django_db
def test_cant_be_refunded_if_not_payment():
    transaction = TransactionFactory(
        status=Transaction.Status.COMPLETED, type=Transaction.Type.REFUND
    )

    assert transaction.can_be_refunded() is False
    with pytest.raises(PaymentException) as exception:
        transaction.can_be_refunded(raises=True)
    assert exception.value.message == "A refund can't be refunded"


@pytest.mark.django_db
def test_cant_be_refunded_if_provider_not_refundable():
    transaction = TransactionFactory(
        status=Transaction.Status.COMPLETED, provider_name="SQUARE_ONLINE"
    )

    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider",
        new_callable=PropertyMock(
            return_value=mock_payment_method(is_refundable=False)
        ),
    ):
        assert transaction.can_be_refunded() is False
        with pytest.raises(PaymentException) as exception:
            transaction.can_be_refunded(raises=True)
        assert exception.value.message == "A SQUARE_ONLINE payment can't be refunded"


@pytest.mark.django_db
def test_can_be_refunded():
    transaction = TransactionFactory(status=Transaction.Status.COMPLETED)

    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider",
        new_callable=PropertyMock(return_value=mock_payment_method(is_refundable=True)),
    ):
        assert transaction.can_be_refunded() is True
        assert transaction.can_be_refunded(raises=True) is True


@pytest.mark.django_db
def test_refund_payment_with_provider():
    """
    When refund is called on a provider, check the refund method of the
    provided refund provider is called.
    """
    payment = TransactionFactory()
    refund_method = mock_refund_method()
    default_refund_method = mock_refund_method()
    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider",
        new_callable=PropertyMock,
    ) as p_mock, mock.patch.object(
        payment, "can_be_refunded", return_value=True
    ) as can_be_refunded_mock:
        p_mock.return_value = mock_payment_method(
            is_refundable=True,
            automatic_refund_provider=default_refund_method,
        )
        payment.refund(refund_method)

        # Assert we check it can be refunded
        can_be_refunded_mock.assert_called_once_with(
            refund_provider=refund_method, raises=True
        )

        # Assert the refund method on the correct provider is called
        refund_method.refund.assert_called_once_with(payment)
        default_refund_method.refund.assert_not_called()


@pytest.mark.django_db
def test_refund_payment_with_default_provider():
    payment = TransactionFactory()
    refund_method = mock_refund_method()
    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider",
        new_callable=PropertyMock,
    ) as p_mock, mock.patch.object(
        payment, "can_be_refunded", return_value=True
    ) as can_be_refunded_mock:
        p_mock.return_value = mock_payment_method(
            is_refundable=True,
            automatic_refund_provider=refund_method,
        )
        payment.refund()

        # Assert we check it can be refunded
        can_be_refunded_mock.assert_called_once_with(refund_provider=None, raises=True)
        refund_method.refund.assert_called_once_with(payment)


@pytest.mark.django_db
def test_refund_payment_with_no_auto_refund_method():
    payment = TransactionFactory(provider_name="abc")
    with mock.patch(
        "uobtheatre.payments.models.Transaction.provider",
        new_callable=PropertyMock,
    ) as p_mock, mock.patch.object(payment, "can_be_refunded", return_value=True):
        p_mock.return_value = mock_payment_method(
            is_refundable=True, automatic_refund_provider=None
        )

        with pytest.raises(PaymentException) as exc:
            payment.refund()

        assert exc.value.message == "A abc payment cannot be automatically refunded"


@pytest.mark.django_db
def test_notify_user_refund_email(mailoutbox):
    transaction = TransactionFactory(
        type=Transaction.Type.REFUND, status=Transaction.Status.PENDING
    )

    transaction.notify_user()
    assert len(mailoutbox) == 0

    transaction.status = Transaction.Status.COMPLETED

    transaction.notify_user()
    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "Refund successfully processed"
