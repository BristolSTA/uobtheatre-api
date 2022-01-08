import pytest
from django.core.exceptions import ValidationError

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.test.factories import PaymentFactory
from uobtheatre.productions.models import Production


@pytest.mark.django_db
@pytest.mark.parametrize("with_pending_payment", [False, True])
def test_production_pre_save_closed_signal(with_pending_payment):
    payment = PaymentFactory(
        pay_object=BookingFactory(),
        status=Transaction.PaymentStatus.PENDING
        if with_pending_payment
        else Transaction.PaymentStatus.COMPLETED,
    )

    # Create a payment that is always complete
    PaymentFactory(
        pay_object=payment.pay_object,
    )
    production = payment.pay_object.performance.production
    assert production.status == Production.Status.PUBLISHED

    def set_to_closed():
        production.status = Production.Status.CLOSED
        production.save()

    if with_pending_payment:
        with pytest.raises(ValidationError):
            set_to_closed()
    else:
        set_to_closed()
