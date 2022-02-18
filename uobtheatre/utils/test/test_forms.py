from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.productions.admin import PerformanceAdmin
from uobtheatre.productions.models import Performance
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.forms import SendEmailForm


# pylint: disable=protected-access
@pytest.mark.django_db
def test_generate_user_reason():
    user = UserFactory()

    booking_1 = BookingFactory(user=user)
    assert (
        PerformanceAdmin._generate_user_reason(
            Performance.objects.filter(pk__in=[booking_1.performance.pk]), user
        )
        == f"You are receiving this email as you have a booking for {str(booking_1.performance)}."
    )

    BookingFactory(user=user, performance=booking_1.performance)
    assert (
        PerformanceAdmin._generate_user_reason(
            Performance.objects.filter(pk__in=[booking_1.performance.pk]), user
        )
        == f"You are receiving this email as you have bookings for {str(booking_1.performance)}."
    )

    booking_2 = BookingFactory(user=user)
    assert (
        PerformanceAdmin._generate_user_reason(
            Performance.objects.filter(
                pk__in=[booking_1.performance.pk, booking_2.performance.pk]
            ),
            user,
        )
        == f"You are receiving this email as you have bookings for the following performances: {str(booking_1.performance)}, {str(booking_2.performance)}."
    )


@pytest.mark.parametrize(
    "is_valid, user_reasons_generator, user_reason",
    [
        (True, None, None),
        (True, None, "My reason"),
        (False, None, "My reason"),
        (True, MagicMock(), "My reason"),
    ],
)
@pytest.mark.django_db
def test_send_email_form_submit(is_valid, user_reasons_generator, user_reason):
    form = SendEmailForm(
        {
            "message": "My Message",
            "subject": "My Subject",
            "users": [UserFactory()],
            "user_reason": user_reason,
        },
        initial={
            "lgtm": True,
        },
    )
    form.is_valid()
    form.user_reason_generator = user_reasons_generator

    with patch.object(form, "is_valid", return_value=is_valid):
        if not is_valid:
            with pytest.raises(ValidationError):
                form.submit()

            if user_reasons_generator:
                assert user_reasons_generator.call_count == 1
        else:
            with patch(
                "uobtheatre.mail.composer.MassMailComposer.send_async"
            ) as send_mock:
                form.submit()
            send_mock.assert_called_once()
