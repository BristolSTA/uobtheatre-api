from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from uobtheatre.payments.models import Transaction
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import (
    Card,
    Cash,
    ManualRefund,
    PaymentProvider,
    RefundProvider,
    SquareOnline,
    SquareRefund,
)


def test_refund_method_all():
    assert RefundProvider.__all__ == [ManualRefund, SquareRefund]


@pytest.mark.parametrize(
    "payment_provider, refund_provider, is_valid",
    [
        (SquareOnline, SquareRefund(idempotency_key="abc"), True),
        (Cash, SquareRefund(idempotency_key="abc"), False),
    ],
)
def test_is_valid_refund_provider(payment_provider, refund_provider, is_valid):
    assert payment_provider.is_valid_refund_provider(refund_provider) == is_valid


@pytest.mark.parametrize(
    "payment_method, automatic_refund_method_type",
    [(SquareOnline, SquareRefund), (Cash, None)],
)
def test_automatic_refund_method(payment_method, automatic_refund_method_type):
    if automatic_refund_method_type is None:
        assert payment_method.automatic_refund_provider is None
    else:
        assert isinstance(
            payment_method.automatic_refund_provider, automatic_refund_method_type
        )


@pytest.mark.parametrize(
    "payment_method, is_auto_refundable", [(SquareOnline, True), (Cash, False)]
)
def test_is_auto_refundable(payment_method, is_auto_refundable):
    assert payment_method.is_auto_refundable == is_auto_refundable


###
# Manual Refund RefundMethod
###


@pytest.mark.django_db
def test_manual_refund_method_refund():
    refund_payment = TransactionFactory(
        value=100,
        provider_fee=10,
        app_fee=20,
        provider_name=Cash.name,
        status=Transaction.Status.COMPLETED,
    )
    ManualRefund().refund(refund_payment)

    assert Transaction.objects.count() == 2

    payment = Transaction.objects.last()
    assert payment.value == -100
    assert payment.app_fee == -20
    assert payment.provider_fee == -10
    assert payment.provider_name == ManualRefund.name
    assert payment.type == Transaction.Type.REFUND


###
# Square Refund RefundMethod
###


@pytest.mark.django_db
def test_square_refund_refund(mock_square):
    idempotency_key = str(uuid4())
    refund_method = SquareRefund(idempotency_key=idempotency_key)

    refund_method.create_payment_object = MagicMock()
    payment = TransactionFactory()

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        status_code=200,
        success=True,
        body={
            "refund": {
                "id": "abc",
                "status": "PENDING",
                "amount_money": {"amount": 100, "currency": "GBP"},
                "payment_id": "abc",
                "order_id": "nRDUxsrkGgorM3g8AT64kCLBLa4F",
                "created_at": "2021-12-30T10:40:54.672Z",
                "updated_at": "2021-12-30T10:40:54.672Z",
                "location_id": "LN9PN3P67S0QV",
            }
        },
    ) as mock:
        refund_method.refund(payment)

    refund_method.create_payment_object.assert_called_once_with(
        payment.pay_object,
        -100,
        None,
        provider_transaction_id="abc",
        currency="GBP",
        status=Transaction.Status.PENDING,
    )
    mock.assert_called_once_with(
        {
            "idempotency_key": idempotency_key,
            "amount_money": {"amount": payment.value, "currency": payment.currency},
            "payment_id": payment.provider_transaction_id,
        }
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data_fees, data_status",
    [
        ([1, 2, 3], "COMPLETED"),
        (None, "COMPLETED"),
        (None, "PENDING"),
        ([1], "PENDING"),
    ],
)
def test_square_online_sync_transaction(data_fees, data_status):
    payment = TransactionFactory(status=Transaction.Status.PENDING, provider_fee=None)

    data = {
        "status": data_status,
    }

    if data_fees:
        data["processing_fee"] = [
            {
                "amount_money": {"amount": fee, "currency": "GBP"},
            }
            for fee in data_fees
        ]

    SquareRefund.sync_transaction(payment, data)

    payment.refresh_from_db()
    if data_status == "COMPLETED":
        assert payment.status == Transaction.Status.COMPLETED
    else:
        assert payment.status == Transaction.Status.PENDING

    if data_fees:
        assert payment.provider_fee == sum(data_fees)
    else:
        assert payment.provider_fee is None


@pytest.mark.django_db
@pytest.mark.parametrize("with_data", [False, True])
def test_square_refund_sync_payment(mock_square, with_data):
    payment = TransactionFactory(
        value=-100,
        provider_fee=None,
        provider_name=SquareRefund.name,
        status=Transaction.Status.PENDING,
    )
    data = {
        "id": "abc",
        "status": "COMPLETED",
        "processing_fee": [{"amount_money": {"amount": -10, "currency": "GBP"}}],
    }
    with mock_square(
        SquareRefund.client.refunds,
        "get_payment_refund",
        body={"refund": data},
        success=True,
    ):
        payment.sync_transaction_with_provider(data=data if with_data else None)
        payment.refresh_from_db()
    assert payment.provider_fee == -10
    assert payment.status == Transaction.Status.COMPLETED
