from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import (
    Cash,
    ManualRefund,
    PaymentMethod,
    RefundMethod,
    SquareOnline,
    SquareRefund,
)
from uobtheatre.payments.test.factories import PaymentFactory


def test_refund_method_all():
    assert RefundMethod.__all__ == [ManualRefund, SquareRefund]


def test_refundable_payment_methods():
    assert PaymentMethod.refundable_payment_methods == [
        SquareOnline
    ]  # pylint: disable=comparison-with-callable


def test_auto_refundable_payment_methods():
    assert PaymentMethod.auto_refundable_payment_methods == [
        SquareOnline
    ]  # pylint: disable=comparison-with-callable


@pytest.mark.parametrize(
    "payment_method, automatic_refund_method_type",
    [(SquareOnline, SquareRefund), (Cash, None)],
)
def test_automatic_refund_method(payment_method, automatic_refund_method_type):
    if automatic_refund_method_type is None:
        assert payment_method.automatic_refund_method is None
    else:
        assert isinstance(
            payment_method.automatic_refund_method, automatic_refund_method_type
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
    refund_payment = PaymentFactory(
        value=100,
        provider_fee=10,
        app_fee=20,
        provider=Cash.name,
        status=Payment.PaymentStatus.COMPLETED,
    )
    ManualRefund().refund(refund_payment)

    assert Payment.objects.count() == 2

    payment = Payment.objects.last()
    assert payment.value == -100
    assert payment.app_fee == -20
    assert payment.provider_fee == -10
    assert payment.provider == ManualRefund.name
    assert payment.type == Payment.PaymentType.REFUND


###
# Square Refund RefundMethod
###


@pytest.mark.django_db
def test_square_refund_refund(mock_square):
    idempotency_key = str(uuid4())
    refund_method = SquareRefund(idempotency_key=idempotency_key)

    refund_method.create_payment_object = MagicMock()
    payment = PaymentFactory()

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
        provider_payment_id="abc",
        currency="GBP",
        status=Payment.PaymentStatus.PENDING,
    )
    mock.assert_called_once_with(
        {
            "idempotency_key": idempotency_key,
            "amount_money": {"amount": payment.value, "currency": payment.currency},
            "payment_id": payment.provider_payment_id,
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
    payment = PaymentFactory(status=Payment.PaymentStatus.PENDING, provider_fee=None)

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
        assert payment.status == Payment.PaymentStatus.COMPLETED
    else:
        assert payment.status == Payment.PaymentStatus.PENDING

    if data_fees:
        assert payment.provider_fee == sum(data_fees)
    else:
        assert payment.provider_fee is None


@pytest.mark.django_db
@pytest.mark.parametrize("with_data", [False, True])
def test_square_refund_sync_payment(mock_square, with_data):
    payment = PaymentFactory(
        value=-100,
        provider_fee=None,
        provider=SquareRefund.name,
        status=Payment.PaymentStatus.PENDING,
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
        payment.sync_payment_with_provider(data=data if with_data else None)
        payment.refresh_from_db()
    assert payment.provider_fee == -10
    assert payment.status == Payment.PaymentStatus.COMPLETED
