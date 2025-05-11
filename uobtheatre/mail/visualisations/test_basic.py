# Use pytest functionality to generate HTML emails in the visualisations folder for generation

import pytest
import os

import factory
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.utils.lang import pluralize

from uobtheatre.mail.composer import (MailComposer)

root = "./uobtheatre/mail/visualisations/basic/"

mountainImage = "https://media.gettyimages.com/id/1211045588/photo/beautiful-winter-mountain-landscape-with-snow-and-glacier-lake.jpg?b=1&s=1024x1024&w=gi&k=20&c=gjiSUA2OVP3s8zJkmJDsBL2V80Hprvjdv5ZdEkV3VuE="


def write_html_file(mail, filename):
    # Delete the existing file
    if not os.path.exists(root + filename):
        with open(root + filename, "x") as f:
            f.write(mail.to_html())
    else:
        with open(root + filename, "w") as f:
            f.write(mail.to_html())

@pytest.mark.django_db
def test_simple_email():

    test_mail = (
        MailComposer()
        .heading("This is a heading")
        .line("This is a paragraph")
        .rule()
        .html("<b>Bold!</b>")
        .image(mountainImage)
        .line("This is another paragraph")
        .action("https://example.org/call/to/action", "Call to Action")
        .line("This is the final paragraph")
    )

    write_html_file(test_mail, "simple_email.html")


@pytest.mark.django_db
def test_booking_confirmation_email():
    """
    Send email confirmation which includes a link to the booking.
    """
    composer = MailComposer()

    booking = BookingFactory()

    composer.line(
        "Your booking to %s has been confirmed!" % booking.performance.production.name
    )

    if booking.performance.production.featured_image:
        # composer.image(booking.performance.production.featured_image.file.url)
        composer.image(mountainImage)

    composer.line(
        (
            "This event opens at %s for a %s start. Please bring your tickets (printed or on your phone) or your booking reference (<strong>%s</strong>)."
            if booking.user.status.verified  # type: ignore
            else "This event opens at %s for a %s start. Please bring your booking reference (<strong>%s</strong>)."
        )
        % (
            booking.performance.doors_open.astimezone(  # type: ignore
                booking.performance.venue.address.timezone  # type: ignore
            ).strftime("%d %B %Y %H:%M %Z"),
            booking.performance.start.astimezone(  # type: ignore
                booking.performance.venue.address.timezone  # type: ignore
            ).strftime("%H:%M %Z"),
            booking.reference,
        )
    )

    composer.action(booking.web_tickets_path, "View Tickets")

    if booking.user.status.verified:  # type: ignore
        composer.action("/user/booking/%s" % booking.reference, "View Booking")

    # If this booking includes a payment, we will include details of this payment as a reciept
    payment = TransactionFactory()

    composer.heading("Payment Information").line(
        f"{payment.value_currency} paid ({payment.provider.description}{' - ID ' + payment.provider_transaction_id if payment.provider_transaction_id else '' })"
    )

    composer.line(
        "If you have any accessability concerns, or otherwise need help, please contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>."
    )

    write_html_file(composer, "booking_confirmation.html")


@pytest.mark.django_db
def test_booking_accessibility_info_email():

    booking = BookingFactory()

    mail = (
        MailComposer()
        .greeting()
        .line(
            f"A booking has been created for {booking.performance} with the following accessibility information:"
        )
        .line(f"'{booking.accessibility_info}'")
        .action(
            f"/administration/productions/{booking.performance.production.slug}/bookings/{booking.reference}",
            "View Booking Details",
        )
    )

    write_html_file(mail, "accessibility_info.html")


@pytest.mark.django_db
def test_payable_refund_initiated_email():

    authorizing_user = UserFactory()
    models = [BookingFactory(), BookingFactory()]
    refund_type = "Full"

    mail = (
        MailComposer()
        .greeting()
        .line(
            f"{refund_type} refund(s) have been initiated for the following {pluralize('item', models)}:"
        )
        .line(
            ", ".join(
                f"{model.__class__.__name__} {model} ({model.pk})" for model in models
            )
        )
        .line(
            f"This action was requested by {authorizing_user.full_name} ({authorizing_user.email})"
        )
    )

    write_html_file(mail, "full_refund.html")


@pytest.mark.django_db
def test__production_approved_email():

    user = UserFactory()
    production = ProductionFactory()

    """Send a production approval email"""
    mail = MailComposer()
    mail.greeting(user).line(
        f"Your production '{production.name}' has been approved."
    ).line(
        "You may now create complimentry bookings and, when ready, make it public, by going to the production control panel."
    ).action(
        f"/administration/productions/{production.slug}",
        "Goto Production Control Panel",
    )

    write_html_file(mail, "production_approved.html")
