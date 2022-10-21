import datetime

import pytest
from django.utils import timezone

import uobtheatre.bookings.emails as booking_emails
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.payments import transaction_providers
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import AddressFactory, VenueFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "with_payment, provider_transaction_id, with_image",
    [(True, "SQUARE_PAYMENT_ID", True), (True, None, False), (False, None, True)],
)
def test_send_confirmation_email(
    mailoutbox, with_payment, provider_transaction_id, with_image
):
    image = ImageFactory() if with_image else None
    production = ProductionFactory(name="Legally Ginger", featured_image=image)
    venue = VenueFactory(address=AddressFactory(latitude=51.4, longitude=-2.61))
    performance = PerformanceFactory(
        venue=venue,
        doors_open=datetime.datetime(
            day=4,
            month=11,
            year=2021,
            hour=18,
            minute=15,
            tzinfo=timezone.get_current_timezone(),
        ),
        start=datetime.datetime(
            day=4,
            month=11,
            year=2021,
            hour=19,
            minute=15,
            tzinfo=timezone.get_current_timezone(),
        ),
        production=production,
    )
    booking = BookingFactory(
        status=Payable.Status.IN_PROGRESS,
        reference="abc",
        performance=performance,
    )
    booking.user.status.verified = True

    payment = (
        TransactionFactory(
            pay_object=booking,
            value=1000,
            provider_name=transaction_providers.SquareOnline.name,
            provider_transaction_id=provider_transaction_id,
        )
        if with_payment
        else None
    )

    booking_emails.send_booking_confirmation_email(booking, payment)

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.subject == "Your booking is confirmed!"
    assert "View Booking (https://example.com/user/booking/abc" in email.body
    assert (
        "View Tickets (https://example.com%s" % booking.web_tickets_path in email.body
    )
    assert "Legally Ginger" in email.body
    assert "opens at 04 November 2021 18:15 GMT for a 19:15 GMT start" in email.body
    if with_payment:
        assert "Payment Information" in email.body
        assert "10.00 GBP" in email.body
        assert (
            "(Square online card payment - ID SQUARE_PAYMENT_ID)"
            if provider_transaction_id
            else "(Square online card payment)" in email.body
        )
    else:
        assert "Payment Information" not in email.body


@pytest.mark.django_db
def test_send_confirmation_email_for_anonymous(mailoutbox):
    production = ProductionFactory(name="Legally Ginger")
    venue = VenueFactory(address=AddressFactory(latitude=51.4, longitude=-2.61))
    performance = PerformanceFactory(
        doors_open=datetime.datetime(
            day=20,
            month=10,
            year=2021,
            hour=18,
            minute=15,
            tzinfo=timezone.get_current_timezone(),
        ),
        start=datetime.datetime(
            day=20,
            month=10,
            year=2021,
            hour=19,
            minute=15,
            tzinfo=timezone.get_current_timezone(),
        ),
        production=production,
        venue=venue,
    )
    booking = BookingFactory(
        status=Payable.Status.IN_PROGRESS,
        reference="abc",
        performance=performance,
    )

    booking_emails.send_booking_confirmation_email(booking)

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.subject == "Your booking is confirmed!"
    assert "View Booking (https://example.com/user/booking/abc" not in email.body
    assert (
        "View Tickets (https://example.com%s" % booking.web_tickets_path in email.body
    )
    assert "Legally Ginger" in email.body
    assert "opens at 20 October 2021 19:15 BST for a 20:15 BST start" in email.body
    assert "reference (abc)" in email.body


@pytest.mark.django_db
def test_send_booking_accessibility_info_email(mailoutbox):
    booking = BookingFactory(
        accessibility_info="Some details about accessibility concerns"
    )
    UserFactory(email="user1@example.org").assign_perm(
        "view_bookings", booking.performance.production
    )
    UserFactory(email="user2@example.org").assign_perm(
        "view_production", booking.performance.production
    )
    booking.performance.production.contact_email = "production@example.org"
    booking.performance.production.save()

    booking_emails.send_booking_accessibility_info_email(booking)

    assert len(mailoutbox) == 2
    assert mailoutbox[0].to == ["production@example.org"]
    assert mailoutbox[1].to == ["user1@example.org"]
    mail = mailoutbox[0]
    assert (
        mail.subject == f"Accessibility alert for {booking.performance.production.name}"
    )
    assert "Some details about accessibility concerns" in mail.body
