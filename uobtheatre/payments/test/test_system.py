# mypy: disable-error-code="attr-defined, union-attr, arg-type, assignment"
import uuid

import pytest
from square import Square as Client

from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.transaction_providers import SquareOnline

pytestmark = pytest.mark.system_test


@pytest.mark.django_db
@pytest.mark.square_integration
def test_create_and_refund_booking(square_client: Client):
    # Create a booking with a seat costing 1200 and a misc cost of 100
    ValueMiscCostFactory(value=100)
    booking = BookingFactory(status=Payable.Status.IN_PROGRESS)
    psg = PerformanceSeatingFactory(performance=booking.performance, price=1200)
    TicketFactory(booking=booking, seat_group=psg.seat_group)

    payment_method = SquareOnline(
        nonce="cnon:card-nonce-ok", idempotency_key=str(uuid.uuid4())
    )
    booking.pay(payment_method)

    assert Transaction.objects.count() == 1
    payment = Transaction.objects.first()
    assert payment.value == 1300
    assert payment.app_fee == 100
    # This is async so should not be set yet (set by the webhooks)
    assert payment.provider_fee is None

    response = square_client.payments.get(payment.provider_transaction_id)

    square_payment = response.payment
    assert square_payment.amount_money.amount == 1300

    # Refund the payment
    payment.refund()

    assert Transaction.objects.count() == 2
    refund = Transaction.objects.latest("created_at")

    assert refund.value == -1300
    assert refund.app_fee == -100
    assert refund.status == Transaction.Status.PENDING

    response = square_client.refunds.get(refund.provider_transaction_id)

    square_refund = response.refund
    assert square_refund.amount_money.amount == 1300
