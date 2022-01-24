from unittest.mock import patch

import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "can_be_refunded,send_email", [(True, False), (False, True), (True, True)]
)
def test_payable_refund_task(mailoutbox, can_be_refunded, send_email):
    pay_object = BookingFactory()
    payment_1 = TransactionFactory(pay_object=pay_object)
    payment_2 = TransactionFactory(pay_object=pay_object)
    TransactionFactory()  # Payment not associated with booking

    with patch.object(
        Booking,
        "validate_cant_be_refunded",
        side_effect=(CantBeRefundedException if not can_be_refunded else None),
        return_value=None,
    ), patch(
        "uobtheatre.payments.models.Transaction.refund", autospec=True
    ) as payment_refund:

        def test():
            pay_object.refund(UserFactory(), send_admin_email=send_email)

        if not can_be_refunded:
            with pytest.raises(CantBeRefundedException):
                test()
        else:
            test()

        assert payment_refund.call_count == (2 if can_be_refunded else 0)
        assert len(mailoutbox) == (1 if can_be_refunded and send_email else 0)
        if can_be_refunded:
            payment_refund.assert_any_call(payment_1)
            payment_refund.assert_any_call(payment_2)
