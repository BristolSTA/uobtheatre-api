from unittest.mock import patch

import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.signals import on_payment_save_callback
from uobtheatre.payments.test.factories import TransactionFactory


@pytest.mark.django_db
def test_payment_model_post_save_status_update(mailoutbox):
    booking = BookingFactory(status=Payable.PayableStatus.PAID)
    booking.user.email = "myuser@example.org"
    TransactionFactory(value=200, pay_object=booking)

    # Add a refund payment. Should set the status initially to locked, and to refunded once it is completed
    with patch(
        "uobtheatre.payments.signals.on_payment_save_callback",
        wraps=on_payment_save_callback,
    ) as mock:
        refund_payment = TransactionFactory(
            value=-200,
            pay_object=booking,
            type=Transaction.Type.REFUND,
            status=Transaction.Status.PENDING,
        )
        mock.assert_called_once()

    assert booking.status == Payable.PayableStatus.LOCKED
    assert len(mailoutbox) == 0

    # Now update that payment to completed
    with patch(
        "uobtheatre.payments.signals.on_payment_save_callback",
        wraps=on_payment_save_callback,
    ) as mock:
        refund_payment.status = Transaction.Status.COMPLETED
        refund_payment.save()
        mock.assert_called_once()
    assert len(mailoutbox) == 1  # Email confirming successful refund
    assert mailoutbox[0].subject == "Refund successfully processed"
    assert mailoutbox[0].to[0] == "myuser@example.org"
    assert booking.status == Payable.PayableStatus.REFUNDED
