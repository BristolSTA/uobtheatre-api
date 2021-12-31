from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import SquareRefund
from uobtheatre.payments.test.factories import PaymentFactory

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
def test_square_online_update_refund(data_fees, data_status):
    payment = PaymentFactory(status=Payment.PaymentStatus.PENDING, provider_fee=None)

    data = {
        "object": {
            "refund": {
                "status": data_status,
            }
        }
    }

    if data_fees:
        data["object"]["refund"]["processing_fee"] = [
            {
                "amount_money": {"amount": fee, "currency": "GBP"},
            }
            for fee in data_fees
        ]

    SquareRefund.update_refund(payment, data)

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
