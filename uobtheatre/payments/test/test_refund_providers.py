from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from square.types.refund_payment_response import RefundPaymentResponse
from square.types.payment_refund import PaymentRefund
from square.types.processing_fee import ProcessingFee

from uobtheatre.payments.models import Transaction
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import (
    Card,
    Cash,
    ManualCardRefund,
    PaymentProvider,
    RefundProvider,
    SquareOnline,
    SquareRefund,
)
from uobtheatre.utils.exceptions import PaymentException


def test_refund_method_all():
    assert RefundProvider.__all__ == [ManualCardRefund, SquareRefund]


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
    ManualCardRefund().refund(refund_payment)

    assert Transaction.objects.count() == 2

    payment = Transaction.objects.latest("created_at")
    assert payment.value == -100
    assert payment.app_fee == -20
    assert payment.provider_fee == -10
    assert payment.provider_name == ManualCardRefund.name
    assert payment.type == Transaction.Type.REFUND


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value,app_fee,custom_refund_amount,expected_app_fee",
    [(100, 20, 90, -10), (100, 20, 80, 0), (100, 0, 90, None)],
)
def test_manual_refund_method_custom_amount_refund(
    value, app_fee, custom_refund_amount, expected_app_fee
):
    refund_payment = TransactionFactory(
        value=value,
        provider_fee=10,
        app_fee=app_fee,
        provider_name=Cash.name,
        status=Transaction.Status.COMPLETED,
    )
    ManualCardRefund().refund(refund_payment, custom_refund_amount)

    assert Transaction.objects.count() == 2

    payment = Transaction.objects.latest("created_at")
    assert payment.value == -custom_refund_amount
    assert payment.app_fee == expected_app_fee
    assert payment.provider_fee == -10
    assert payment.provider_name == ManualCardRefund.name
    assert payment.type == Transaction.Type.REFUND


@pytest.mark.django_db
def test_manual_refund_method_custom_amount_too_high_refund():
    refund_payment = TransactionFactory(
        value=100,
        provider_fee=10,
        app_fee=20,
        provider_name=Cash.name,
        status=Transaction.Status.COMPLETED,
    )
    with pytest.raises(PaymentException):
        ManualCardRefund().refund(refund_payment, 110)


###
# Square Refund RefundMethod
###


@pytest.mark.django_db
def test_square_refund_refund(mock_square):
    idempotency_key = str(uuid4())
    refund_method = SquareRefund(idempotency_key=idempotency_key)

    refund_method.create_payment_object = MagicMock()
    payment = TransactionFactory(value=100, provider_fee=10, app_fee=20)

    mock_response = RefundPaymentResponse(
        refund={
            "id": "abc",
            "status": "PENDING",
            "amount_money": {"amount": 100, "currency": "GBP"},
            "payment_id": "abc",
            "order_id": "nRDUxsrkGgorM3g8AT64kCLBLa4F",
            "created_at": "2021-12-30T10:40:54.672Z",
            "updated_at": "2021-12-30T10:40:54.672Z",
            "location_id": "LN9PN3P67S0QV",
        }
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ) as mock:
        refund_method.refund(payment)

    refund_method.create_payment_object.assert_called_once_with(
        payment.pay_object,
        -100,
        -20,
        provider_transaction_id="abc",
        currency="GBP",
        status=Transaction.Status.PENDING,
    )
    mock.assert_called_once_with(
        idempotency_key = idempotency_key,
        amount_money = {"amount": payment.value, "currency": payment.currency},
        payment_id = payment.provider_transaction_id,
        reason = f"Refund for {payment.pay_object.payment_reference_id}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value,app_fee,custom_refund_amount,expected_app_fee",
    [(100, 20, 90, -10), (100, 20, 80, 0), (100, 0, 90, None)],
)
def test_square_refund_custom_amount_refund(
    mock_square, value, app_fee, custom_refund_amount, expected_app_fee
):
    idempotency_key = str(uuid4())
    refund_method = SquareRefund(idempotency_key=idempotency_key)

    refund_method.create_payment_object = MagicMock()
    payment = TransactionFactory(value=value, provider_fee=10, app_fee=app_fee)

    mock_response = RefundPaymentResponse(
        refund={
            "id": "abc",
            "status": "PENDING",
            "amount_money": {"amount": custom_refund_amount, "currency": "GBP"},
            "payment_id": "abc",
            "order_id": "nRDUxsrkGgorM3g8AT64kCLBLa4F",
            "created_at": "2021-12-30T10:40:54.672Z",
            "updated_at": "2021-12-30T10:40:54.672Z",
            "location_id": "LN9PN3P67S0QV",
        }
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ) as mock:
        refund_method.refund(payment)

    refund_method.create_payment_object.assert_called_once_with(
        payment.pay_object,
        -custom_refund_amount,
        expected_app_fee,
        provider_transaction_id="abc",
        currency="GBP",
        status=Transaction.Status.PENDING,
    )
    mock.assert_called_once_with(
        idempotency_key = idempotency_key,
        amount_money = {"amount": payment.value, "currency": payment.currency},
        payment_id = payment.provider_transaction_id,
        reason = f"Refund for {payment.pay_object.payment_reference_id}"
    )


@pytest.mark.django_db
def test_square_refund_custom_amount_too_high_refund(mock_square):
    idempotency_key = str(uuid4())
    refund_method = SquareRefund(idempotency_key=idempotency_key)

    refund_method.create_payment_object = MagicMock()
    payment = TransactionFactory()

    mock_response = RefundPaymentResponse(
        refund={
            "id": "abc",
            "status": "PENDING",
            "amount_money": {"amount": payment.value + 1, "currency": "GBP"},
            "payment_id": "abc",
            "order_id": "nRDUxsrkGgorM3g8AT64kCLBLa4F",
            "created_at": "2021-12-30T10:40:54.672Z",
            "updated_at": "2021-12-30T10:40:54.672Z",
            "location_id": "LN9PN3P67S0QV",
        }
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response
    ):
        with pytest.raises(PaymentException):
            refund_method.refund(payment, payment.value + 1)


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

    data = PaymentRefund(
        status=data_status,
        id="abc",
        amount_money={"amount": 10, "currency": "GBP"},
        processing_fee=[
            ProcessingFee(
                amount_money={"amount": fee, "currency": "GBP"},
            )
            for fee in data_fees if data_fees
        ] if data_fees else None
    )

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
    data = PaymentRefund(
        id="abc",
        status="COMPLETED",
        amount_money={"amount": -10, "currency": "GBP"},
        processing_fee=[
            ProcessingFee(
                amount_money={"amount": -10, "currency": "GBP"},
            )
        ],
    )

    mock_response = RefundPaymentResponse(
        refund=data
    )

    with mock_square(
        SquareRefund.client.refunds,
        "get",
        mock_response
    ):
        payment.sync_transaction_with_provider(data=data if with_data else None)
        payment.refresh_from_db()
    assert payment.provider_fee == -10
    assert payment.status == Transaction.Status.COMPLETED
