# Use pytest functionality to generate HTML emails in the visualisations folder for generation

import os

import factory
import pytest

from uobtheatre.bookings.test.factories import BookingFactory, TicketFactory
from uobtheatre.mail.composerV2 import *
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.lang import pluralize

root = "./uobtheatre/mail/visualisations/v2/"

mountainImage = "https://media.gettyimages.com/id/1211045588/photo/beautiful-winter-mountain-landscape-with-snow-and-glacier-lake.jpg?b=1&s=1024x1024&w=gi&k=20&c=gjiSUA2OVP3s8zJkmJDsBL2V80Hprvjdv5ZdEkV3VuE="


def write_files(mail, filename):
    # Write both the .html and the .txt files for the html and plaintext visualisations
    for extension in [".html", ".txt"]:
        content = mail.to_html() if extension == ".html" else mail.to_plain_text()

        # Delete the existing file if it already exists
        if not os.path.exists(root + filename + extension):
            with open(root + filename + extension, "x") as f:
                f.write(content)
        else:
            with open(root + filename + extension, "w") as f:
                f.write(content)


@pytest.mark.django_db
def _test_simple_email():

    test_mail = (
        MailComposer.blank([Box(
            Paragraph("This is a test title", "This is a test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines."),
            bgCol="#ffffff"),
            Box(
            Paragraph(title="This is a new test title"),
            bgCol="#ffffff"),
            Box(
            Paragraph(message="This is a new test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines."),
            bgCol="#ffffff")]
        ))

    write_files(test_mail, "simple_email")


@pytest.mark.django_db
def _test_text_only():

    test_mail = MailComposer.textOnly(
        "This is a test title", "<b>This</b> is a test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines.", True)

    write_files(test_mail, "text_only")


@pytest.mark.django_db
def _test_booking_conf():

    booking = BookingFactory()
    payment = TransactionFactory()

    test_mail = MailComposer.blank([

        Paragraph(
            title="Your booking to %s has been confirmed!" % booking.performance.production.name
        ),

        Image(src=mountainImage),

        Paragraph(

            message="This event opens at %s for a %s start. Please bring your tickets (printed or on your phone) or your booking reference (<strong>%s</strong>)."
            if booking.user.status.verified  # type: ignore
            else "This event opens at %s for a %s start. Please bring your booking reference (<strong>%s</strong>)."

            % (
                booking.performance.doors_open.astimezone(  # type: ignore
                    booking.performance.venue.address.timezone  # type: ignore
                ).strftime("%d %B %Y %H:%M %Z"),
                booking.performance.start.astimezone(  # type: ignore
                    booking.performance.venue.address.timezone  # type: ignore
                ).strftime("%H:%M %Z"),
                booking.reference,
            ), htmlSafe=True
        ),

        Button(booking.web_tickets_path, "View Tickets"),

        Button("/user/booking/%s" % booking.reference, "View Booking"),

        Paragraph(title="Payment Information", message=f"{payment.value_currency} paid ({payment.provider.description}{' - ID ' + payment.provider_transaction_id if payment.provider_transaction_id else '' })"
                  ),

        Paragraph(
            message="If you have any accessability concerns, or otherwise need help, please contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>.", htmlSafe=True
        )]
    )

    write_files(test_mail, "booking_conf")


@pytest.mark.django_db
def test_booking_conf_new():

    user = UserFactory()
    user.status.verified = True

    booking = BookingFactory()
    payment = TransactionFactory()

    tickets = [TicketFactory(booking=booking) for _ in range(5)]

    doors = booking.performance.doors_open.astimezone(
        booking.performance.venue.address.timezone).strftime('%A, %d %B %Y at %H:%M (%Z)')
    start = booking.performance.start.astimezone(
        booking.performance.venue.address.timezone).strftime('%A, %d %B %Y at %H:%M (%Z)')



    test_mail = MailComposer.blank([

        Heading(
            title="Your booking to %s has been confirmed!" % booking.performance.production.name
        ),

        Image(src=mountainImage),

        Heading(subtitle="About Your Booking", titleIcon="bookmark"),
        
        Box(
            TimingsBlock(booking.performance)
        ),

        Box(
            BookingBlock(booking)
        ),

        BoxCols([
            RowStack([
                Heading(subsubtitle="Payment Information", titleIcon="trolley"),

                ListItem(message=f"{payment.value_currency} paid", messageIcon="money"),

                ListItem(
                    message=f"{payment.provider.description}{(' - ID ' + payment.provider_transaction_id) if payment.provider_transaction_id else '' }", messageIcon="card"),
            ]),

            AccessibilityBlock()
        ]),

        TicketCodes(booking.reference, [ticket.id for ticket in tickets])
    ]
    )

    write_files(test_mail, "booking_conf_new")
