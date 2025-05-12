from unittest.mock import patch

import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.productions.tasks import refund_performance
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_refund_performance_task(mailoutbox):
    performance = PerformanceFactory()
    booking = BookingFactory(performance=performance)
    BookingFactory()
    auth_user = UserFactory()

    with patch(
        "uobtheatre.bookings.models.Booking.async_refund", autospec=True
    ) as refund_mock:
        refund_performance(performance.pk, auth_user.pk)

    refund_mock.assert_called_once_with(
        booking,
        authorizing_user=auth_user,
        preserve_provider_fees=True,
        preserve_app_fees=False,
    )
    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "[UOB Theatre] Performance Refunds Initiated"
