from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import SquareRefund
from uobtheatre.payments.test.factories import PaymentFactory


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
