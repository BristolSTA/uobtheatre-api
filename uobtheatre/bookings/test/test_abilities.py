import pytest

from uobtheatre.bookings.abilities import ModifyBooking, TransferBooking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.payables import Payable
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,same_user,with_boxoffice_perm,expected",
    (
        (Payable.Status.IN_PROGRESS, False, False, False),
        (Payable.Status.IN_PROGRESS, False, True, True),
        (Payable.Status.IN_PROGRESS, True, False, True),
        (Payable.Status.PAID, True, False, False),
        (Payable.Status.PAID, True, True, False),
        (Payable.Status.CANCELLED, True, True, False),
    ),
)
def test_modify_booking_has_for_obj(status, same_user, with_boxoffice_perm, expected):
    booking_user = UserFactory()
    booking_obj = BookingFactory(status=status, user=booking_user)

    query_user = booking_user if same_user else UserFactory()
    if with_boxoffice_perm:
        query_user.assign_perm(
            "productions.boxoffice", booking_obj.performance.production
        )

    assert ModifyBooking.user_has_for(query_user, booking_obj) is expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,same_user,with_boxoffice_perm,expected",
    (
        (Payable.Status.IN_PROGRESS, False, False, False),
        (Payable.Status.IN_PROGRESS, False, True, False),
        (Payable.Status.IN_PROGRESS, True, False, False),
        (Payable.Status.PAID, True, False, True),
        (Payable.Status.PAID, False, True, True),
        (Payable.Status.CANCELLED, True, True, False),
    ),
)
def test_transfer_booking_has_for_obj(status, same_user, with_boxoffice_perm, expected):
    booking_user = UserFactory()
    booking_obj = BookingFactory(status=status, user=booking_user)

    query_user = booking_user if same_user else UserFactory()
    if with_boxoffice_perm:
        query_user.assign_perm(
            "productions.boxoffice", booking_obj.performance.production
        )

    assert TransferBooking.user_has_for(query_user, booking_obj) is expected
