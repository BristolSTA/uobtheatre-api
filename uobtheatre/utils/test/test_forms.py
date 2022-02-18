import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.productions.admin import PerformanceAdmin
from uobtheatre.productions.models import Performance
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_send_email_form_submit():
    pass


# pylint: disable=protected-access
@pytest.mark.django_db
def test_generate_user_reason():
    user = UserFactory()

    booking_1 = BookingFactory(user=user)
    assert (
        PerformanceAdmin._generate_user_reason(
            Performance.objects.filter(pk__in=[booking_1.performance.pk]), user
        )
        == f"You are reciving this email as you have a booking for {str(booking_1.performance)}."
    )

    BookingFactory(user=user, performance=booking_1.performance)
    assert (
        PerformanceAdmin._generate_user_reason(
            Performance.objects.filter(pk__in=[booking_1.performance.pk]), user
        )
        == f"You are reciving this email as you have bookings for {str(booking_1.performance)}."
    )

    booking_2 = BookingFactory(user=user)
    assert (
        PerformanceAdmin._generate_user_reason(
            Performance.objects.filter(
                pk__in=[booking_1.performance.pk, booking_2.performance.pk]
            ),
            user,
        )
        == f"You are reciving this email as you have bookings for the following performances: {str(booking_1.performance)}, {str(booking_2.performance)}."
    )
