from unittest import mock
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from pytest_django.asserts import assertQuerysetEqual
from square.types.get_payment_response import GetPaymentResponse

from uobtheatre.payments.exceptions import (
    CantBeCanceledException,
    CantBeRefundedException,
)
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.tasks import refund_payment
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
from uobtheatre.utils.test.factories import TaskResultFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value, result",
    [
        (100, "1.00 GBP"),
        (150, "1.50 GBP"),
        (199, "1.99 GBP"),
        (100.1, "1.00 GBP"),
        (-1000, "10.00 GBP"),
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

    mock_response = GetPaymentResponse(
        payment={
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
    )

    with mock_square(SquareOnline.client.payments, "get", response=mock_response):
        payment.sync_transaction_with_provider()

    payment.refresh_from_db()
    assert payment.provider_fee == 58


@pytest.mark.django_db
def test_update_payment_from_square_no_provider_id(mock_square):
    payment = TransactionFactory(provider_fee=0, provider_transaction_id=None)
    with mock_square(
        SquareOnline.client.payments,
        "get",
    ) as mock_get, pytest.raises(PaymentException):
        payment.sync_transaction_with_provider()
    mock_get.assert_not_called()

    assert payment.provider_fee == 0


@pytest.mark.django_db
def test_update_payment_from_square_no_processing_fee(mock_square):
    payment = TransactionFactory(provider_fee=None, provider_transaction_id="abc")

    mock_response = GetPaymentResponse(
        payment={
            "id": "RGdfG3spBBfui4ZJy4HFFogUKjKZY",
            "amount_money": {"amount": 1990, "currency": "GBP"},
            "status": "COMPLETED",
            "delay_duration": "PT168H",
            "source_type": "CARD",
            "total_money": {"amount": 1990, "currency": "GBP"},
            "approved_money": {"amount": 1990, "currency": "GBP"},
        }
    )

    with mock_square(SquareOnline.client.payments, "get", mock_response):
        payment.sync_transaction_with_provider()

    payment.refresh_from_db()
    assert payment.provider_fee is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,fails",
    [
        (Transaction.Status.COMPLETED, True),
        (Transaction.Status.FAILED, True),
        (Transaction.Status.PENDING, False),
    ],
)
def test_cancel(status, fails):
    transaction = TransactionFactory(status=status)
    if fails:
        with pytest.raises(CantBeCanceledException):
            transaction.cancel()
        assert Transaction.objects.filter(pk=transaction.pk).exists()
    else:
        with patch(
            "uobtheatre.payments.transaction_providers.SquareOnline.cancel"
        ) as provider_mock:
            transaction.cancel()
        provider_mock.assert_called_once_with(transaction)


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
    with pytest.raises(CantBeRefundedException) as exception:
        transaction.can_be_refunded(raises=True)
    assert (
        exception.value.message == f"A {status.label.lower()} payment can't be refunded"
    )


@pytest.mark.django_db
def test_transaction_qs_sync():
    transactions = [TransactionFactory() for _ in range(3)]
    with patch(
        "uobtheatre.payments.models.Transaction.sync_transaction_with_provider",
        autospec=True,
    ) as mock_sync:
        Transaction.objects.sync()

    assert mock_sync.call_count == 3
    for transaction in transactions:
        mock_sync.assert_any_call(transaction)


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
        with pytest.raises(CantBeRefundedException) as exception:
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
    with pytest.raises(CantBeRefundedException) as exception:
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
        with pytest.raises(CantBeRefundedException) as exception:
            transaction.can_be_refunded(raises=True)
        assert exception.value.message == "A SQUARE_ONLINE payment can't be refunded"


@pytest.mark.django_db
def test_async_refund():
    transaction = TransactionFactory(id=45)
    with patch.object(refund_payment, "delay") as delay_mock:
        transaction.async_refund()
        delay_mock.assert_called_once_with(45)


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
        payment.refund(refund_provider=refund_method, preserve_provider_fees=False)

        # Assert we check it can be refunded
        can_be_refunded_mock.assert_called_once_with(
            refund_provider=refund_method, raises=True
        )

        # Assert the refund method on the correct provider is called
        refund_method.refund.assert_called_once_with(payment, custom_refund_amount=None)
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
        payment.refund(preserve_provider_fees=False)

        # Assert we check it can be refunded
        can_be_refunded_mock.assert_called_once_with(refund_provider=None, raises=True)
        refund_method.refund.assert_called_once_with(payment, custom_refund_amount=None)


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

        with pytest.raises(CantBeRefundedException) as exc:
            payment.refund()

        assert exc.value.message == "A abc payment cannot be automatically refunded"


@pytest.mark.django_db
def test_refund_payment_with_provider_preserve_provider_fees():
    """
    When a refund is called that preserves provider fees, the refund method
    of the provided refund provider should be called with the correct amount.
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
        payment.refund(refund_provider=refund_method, preserve_provider_fees=True)

        # Assert we check it can be refunded
        can_be_refunded_mock.assert_called_once_with(
            refund_provider=refund_method, raises=True
        )

        expected_refund_amount = payment.value - payment.provider_fee

        # Assert the refund method on the correct provider is called with the correct amount
        refund_method.refund.assert_called_once_with(
            payment, custom_refund_amount=expected_refund_amount
        )
        default_refund_method.refund.assert_not_called()


@pytest.mark.django_db
def test_refund_payment_with_provider_preserve_app_fees():
    """
    When a refund is called that preserves app fees, the refund method
    of the provided refund provider should be called with the correct amount.
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
        payment.refund(
            refund_provider=refund_method,
            preserve_provider_fees=False,
            preserve_app_fees=True,
        )

        # Assert we check it can be refunded
        can_be_refunded_mock.assert_called_once_with(
            refund_provider=refund_method, raises=True
        )

        expected_refund_amount = payment.value - payment.app_fee

        # Assert the refund method on the correct provider is called with the correct amount
        refund_method.refund.assert_called_once_with(
            payment, custom_refund_amount=expected_refund_amount
        )
        default_refund_method.refund.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "provider_fees, app_fees, expected_refund_minus",
    [
        (90, 10, 90),
        (10, 90, 90),
        (90, 90, 90),
        (10, 10, 10),
    ],
)
def test_refund_payment_with_provider_preserve_fees(
    provider_fees, app_fees, expected_refund_minus
):
    """
    When a refund is called that preserves app and provider fees, the refund method
    of the provided refund provider should be called with the correct amount.
    """
    payment = TransactionFactory()

    payment.provider_fee = provider_fees
    payment.app_fee = app_fees
    payment.save()

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
        payment.refund(
            refund_provider=refund_method,
            preserve_provider_fees=True,
            preserve_app_fees=True,
        )

        # Assert we check it can be refunded
        can_be_refunded_mock.assert_called_once_with(
            refund_provider=refund_method, raises=True
        )

        expected_refund_amount = payment.value - expected_refund_minus

        # Assert the refund method on the correct provider is called with the correct amount
        refund_method.refund.assert_called_once_with(
            payment, custom_refund_amount=expected_refund_amount
        )
        default_refund_method.refund.assert_not_called()


@pytest.mark.django_db
def test_negative_refund_amount_throws_error():
    """
    When a refund is called that preserves app and provider fees, the refund method
    of the provided refund provider should be called with the correct amount.
    """
    payment = TransactionFactory(value=20, provider_fee=25)

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
        with pytest.raises(CantBeRefundedException):
            payment.refund(
                refund_provider=refund_method,
                preserve_provider_fees=True,
                preserve_app_fees=True,
            )
            # Assert we check it can be refunded
            can_be_refunded_mock.assert_called_once_with(
                refund_provider=refund_method, raises=True
            )


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


@pytest.mark.django_db
def test_payment_associated_tasks():
    transaction = TransactionFactory(
        type=Transaction.Type.PAYMENT, status=Transaction.Status.COMPLETED
    )
    # Different transaction
    other_transaction = TransactionFactory(
        type=Transaction.Type.PAYMENT, status=Transaction.Status.COMPLETED
    )

    # A related task
    related_task = TaskResultFactory(
        task_name="uobtheatre.payments.tasks.refund_payment",
        task_args=f'"({transaction.id},)"',
    )

    # Unrelated, different transaction
    TaskResultFactory(
        task_name="uobtheatre.payments.tasks.refund_payment",
        task_args=f'"({other_transaction.id},)"',
    )

    # Unrelated, different task type
    TaskResultFactory(
        task_name="uobtheatre.payments.tasks.refund_production",
        task_args=f'"({transaction.id},)"',
    )

    assert list(transaction.qs.associated_tasks()) == [related_task]
