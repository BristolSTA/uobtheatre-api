# Use pytest functionality to generate HTML emails in the visualisations folder for generation

import os

import factory
import pytest
from faker import Faker

from uobtheatre.bookings.test.factories import BookingFactory, TicketFactory
from uobtheatre.mail.composer_v2 import *
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.lang import pluralize

root = "./uobtheatre/mail/visualisations/v2/"

testTrashImage = "https://uobtheatre-api-media.s3.amazonaws.com/media/featuredImage_63661587-ae96-4602-9b9b-e513b1fa360f.jpg"


def write_files(mail, filename):
    # Write both the .html and the .txt files for the html and plaintext visualisations
    for extension in [".html", ".txt"]:
        content = (
            mail.to_html() if extension == ".html" else mail.to_plain_text()
        )

        # Delete the existing file if it already exists
        if not os.path.exists(root + filename + extension):
            with open(root + filename + extension, "x") as f:
                f.write(content)
        else:
            with open(root + filename + extension, "w") as f:
                f.write(content)


@pytest.mark.django_db
def _test_simple_email():

    test_mail = MailComposer.blank(
        [
            Box(
                Paragraph(
                    "This is a test title",
                    "This is a test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines.",
                ),
                bgCol="#ffffff",
            ),
            Box(Paragraph(title="This is a new test title"), bgCol="#ffffff"),
            Box(
                Paragraph(
                    message="This is a new test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines."
                ),
                bgCol="#ffffff",
            ),
        ]
    )

    write_files(test_mail, "simple_email")


@pytest.mark.django_db
def _test_text_only():

    test_mail = MailComposer.text_only(
        "This is a test title",
        "<b>This</b> is a test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines.",
        True,
    )

    write_files(test_mail, "text_only")


@pytest.mark.django_db
def _test_booking_conf():

    booking = BookingFactory()
    payment = TransactionFactory()

    test_mail = MailComposer.blank(
        [
            Paragraph(
                title="Your booking to %s has been confirmed!"
                % booking.performance.production.name
            ),
            Image(src=testTrashImage),
            Paragraph(
                message=(
                    "This event opens at %s for a %s start. Please bring your tickets (printed or on your phone) or your booking reference (<strong>%s</strong>)."
                    if booking.user.status.verified  # type: ignore
                    else "This event opens at %s for a %s start. Please bring your booking reference (<strong>%s</strong>)."
                    % (
                        booking.performance.doors_open.astimezone(  # type: ignore
                            booking.performance.venue.address.timezone  # type: ignore
                        ).strftime(
                            "%d %B %Y %H:%M %Z"
                        ),
                        booking.performance.start.astimezone(  # type: ignore
                            booking.performance.venue.address.timezone  # type: ignore
                        ).strftime("%H:%M %Z"),
                        booking.reference,
                    )
                ),
                htmlSafe=True,
            ),
            Button(booking.web_tickets_path, "View Tickets"),
            Button("/user/booking/%s" % booking.reference, "View Booking"),
            Paragraph(
                title="Payment Information",
                message=f"{payment.value_currency} paid ({payment.provider.description}{' - ID ' + payment.provider_transaction_id if payment.provider_transaction_id else '' })",
            ),
            Paragraph(
                message="If you have any accessability concerns, or otherwise need help, please contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>.",
                htmlSafe=True,
            ),
        ]
    )

    write_files(test_mail, "booking_conf")


@pytest.mark.django_db
def test_booking_conf_new():

    user = UserFactory()
    user.status.verified = True

    booking = BookingFactory()
    payment = TransactionFactory()

    tickets = [TicketFactory(booking=booking) for _ in range(5)]

    stack = [
        Heading(
            title="Your booking to %s has been confirmed!"
            % booking.performance.production.name
        ),
        Image(src=testTrashImage),
        Heading(subtitle="About Your Booking", title_icon="bookmark"),
        Box(TimingsBlock(booking.performance)),
        Box(VenueBlock(booking.performance.venue)),
        Box(BookingBlock(booking)),
        BoxCols(
            [
                PaymentBlock(payment),
                VenueAccessibilityBlock(booking.performance.venue),
            ]
        ),
    ]
    if booking.accessibility_info:
        stack.append(Box(BookingAccessibilityBlock(booking)))
    stack.append(
        TicketCodes(booking.reference, [ticket.id for ticket in tickets])
    )

    test_mail = MailComposer.blank(stack)

    write_files(test_mail, "booking_conf_new")


@pytest.mark.django_db
def test_production_approved_email():
    user = UserFactory()
    production = ProductionFactory()

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Your production '{production.name}' has been approved!",
                title_icon="square-check",
            ),
            Image(src=testTrashImage),
            Greeting(user=user),
            Paragraph(
                message=f"Congratulations! Your production '{production.name}' has been approved. You're on the cusp of going live!"
            ),
            Paragraph(
                message="Now your production is approved, you <b>cannot</b> make any changes to the production details or listing without it being reviewed again. If you need to make any changes, please contact us at <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>.",
                html_safe=True,
            ),
            Box(
                RowStack(
                    [
                        Heading(
                            subsubtitle="You should now:", title_icon="rocket"
                        ),
                        ListItem(
                            title="Triple Check Your Production Details",
                            title_icon="play",
                            message="Make sure all the details are correct, and that your listing looks great. It's easy to fix things now, but once your production is live, things get more difficult!",
                        ),
                        ListItem(
                            title="Edit Permissions",
                            title_icon="play",
                            message="If your show is being put on with an STA crew, you won't need to worry about this, but if you're working at an external venue make sure you've given the right people access to manage your production and operate your box office.",
                        ),
                        ListItem(
                            title="Create Complimentary Bookings",
                            title_icon="play",
                            message="As soon as you make your production live, anybody can book a ticket. If you want to guarantee tickets for certain people, you should create complimentary bookings for them now.",
                        ),
                        ListItem(
                            title="And Make Your Production Live!",
                            title_icon="play",
                        ),
                        Button(
                            f"/administration/productions/{production.slug}",
                            "Go To Production Control Panel",
                        ),
                    ]
                )
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "production_approved_email")


@pytest.mark.django_db
def test_production_needs_changes_email():
    user = UserFactory()
    production = ProductionFactory()

    fake = Faker()
    message = fake.sentence(nb_words=20)

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Your production '{production.name}' needs some changes",
                title_icon="alert-triangle",
            ),
            Image(src=testTrashImage),
            Greeting(user=user),
            Paragraph(
                message=f"We have reviewed your production '{production.name}', and some changes need to be made before we can approve it."
            ),
            Paragraph(
                message="Please review the comments below, and make the required changes. Once you're done, you can resubmit your production for review.",
            ),
            # Note to self: we should make message mandatory when submitting a review
            Box(
                RowStack(
                    [
                        Heading(
                            subsubtitle="Review Comments:",
                            title_icon="comments",
                        ),
                        ListItem(message=message),
                    ]
                )
            ),
            Paragraph(
                message="If you need any help, please contact us at <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>",
                html_safe=True,
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "production_needs_changes_email")


@pytest.mark.django_db
def test_production_ready_for_review_email():
    user = UserFactory()
    production = ProductionFactory()

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"'{production.name}' is ready for review",
                title_icon="rocket",
            ),
            Image(src=testTrashImage),
            Greeting(user=user),
            Paragraph(
                message=f"'{production.name}' has been submitted for review. Please head to the admin control panel, verify the production's details and listing, and either approve or reject."
            ),
            Button(
                f"/administration/productions/{production.slug}",
                "Go To Production Control Panel",
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "production_ready_for_review_email")


@pytest.mark.django_db
def test_mass_email_admin_notification_email():
    user = UserFactory()
    production = ProductionFactory()

    mass_email = MailComposer.blank(
        [
            Heading(
                title=f"'{production.name}' is ready for review",
                title_icon="rocket",
            ),
            Image(src=testTrashImage),
            Greeting(user=user),
            Paragraph(
                message=f"'{production.name}' has been submitted for review. Please head to the admin control panel, verify the production's details and listing, and either approve or reject."
            ),
            Button(
                f"/administration/productions/{production.slug}",
                "Go To Production Control Panel",
            ),
            Closer(),
        ]
    ).to_html()

    test_mail = MailComposer.blank(
        [
            Heading(title=f"New Mass Email Sent", title_icon="envelope"),
            Greeting(user=user),
            # Replace number with {len(django_emails)} when implementing
            Paragraph(message=f"The following mass email was sent 22 times:"),
            Box(HTMLBlock(mass_email), bgCol="#2B303A"),
            Closer(),
        ]
    )

    write_files(test_mail, "mass_email_admin_notification_email")


@pytest.mark.django_db
def test_booking_accessibility_info_email():

    booking = BookingFactory()

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Accessibility Alert for {booking.performance.production.name}",
                title_icon="accessibility",
            ),
            Image(src=testTrashImage),
            Paragraph(
                message=f"A patron has <strong>added</strong> accessibility information for the <strong>{booking.performance.start.strftime('%d/%m/%Y %I:%M %p')}</strong> showing of <strong>{booking.performance.production.name}</strong>.",
                html_safe=True,
            ),
            Paragraph(
                message=f"Please review the booking to see what information has been updated and if any action is required. Ensure you liase with your venue and front of house teams about this: do not assume that they are aware of this change. Please contact the patron directly if you need to discuss this information with them."
            ),
            Paragraph(
                message="<strong>Remember that accessibility information is sensitive and should be treated with care.</strong> Only those who need to know should be informed of this information.",
                html_safe=True,
            ),
            Button(
                f"/administration/productions/{booking.performance.production.slug}/bookings/{booking.reference}",
                "View Booking Details",
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "booking_accessibility_info_email")


@pytest.mark.django_db
def test_booking_accessibility_removed_email():

    booking = BookingFactory()

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Accessibility Alert for {booking.performance.production.name}",
                title_icon="accessibility",
            ),
            Image(src=testTrashImage),
            Paragraph(
                message=f"A patron has <strong>removed</strong> their accessibility information for the <strong>{booking.performance.start.strftime('%d/%m/%Y %I:%M %p')}</strong> showing of <strong>{booking.performance.production.name}</strong>.",
                html_safe=True,
            ),
            Paragraph(
                message=f"Please review the booking to see if any action is required. Ensure you liase with your venue and front of house teams about this: do not assume that they are aware of this change. Please contact the patron directly if you need to discuss this information with them."
            ),
            Paragraph(
                message="<strong>Remember that accessibility information is sensitive and should be treated with care.</strong> Only those who need to know should be informed of this information.",
                html_safe=True,
            ),
            Button(
                f"/administration/productions/{booking.performance.production.slug}/bookings/{booking.reference}",
                "View Booking Details",
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "booking_accessibility_removed_email")


@pytest.mark.django_db
def test_booking_accessibility_updated_email():

    booking = BookingFactory()

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Accessibility Alert for {booking.performance.production.name}",
                title_icon="accessibility",
            ),
            Image(src=testTrashImage),
            Paragraph(
                message=f"A patron has <strong>updated</strong> their accessibility information for the <strong>{booking.performance.start.strftime('%d/%m/%Y %I:%M %p')}</strong> showing of <strong>{booking.performance.production.name}</strong>.",
                html_safe=True,
            ),
            Paragraph(
                message=f"Please review the booking to see what information has been updated and if any action is required. Ensure you liase with your venue and front of house teams about this: do not assume that they are aware of this change. Please contact the patron directly if you need to discuss this information with them."
            ),
            Paragraph(
                message="<strong>Remember that accessibility information is sensitive and should be treated with care.</strong> Only those who need to know should be informed of this information.",
                html_safe=True,
            ),
            Button(
                f"/administration/productions/{booking.performance.production.slug}/bookings/{booking.reference}",
                "View Booking Details",
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "booking_accessibility_updated_email")


@pytest.mark.django_db
def test_email_activation_email():

    user = UserFactory()

    path = "/login/activate"
    token = "token"

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Activate Your Account",
                title_icon="square-check",
            ),
            Greeting(user=user),
            Paragraph(
                message=f"Welcome to UOB Theatre! Please click the button below to activate your account and get started."
            ),
            Paragraph(
                message="If you did not create an account, please ignore this email.",
                html_safe=True,
            ),
            Button(
                f"{path}/{token}",
                "Activate Account",
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "account_activation_email")


@pytest.mark.django_db
def test_password_reset_email():

    user = UserFactory()

    path = "/login/forget"
    token = "token"

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Reset Your Password",
                title_icon="key",
            ),
            Greeting(user=user),
            Paragraph(
                message=f"We received a request to reset your password. Please click the button below to reset your password."
            ),
            Paragraph(
                message="If you did not request a password reset, please ignore this email.",
            ),
            Button(
                f"{path}/{token}",
                "Reset Password",
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "password_reset_email")


@pytest.mark.django_db
def test_performance_sold_out_email():

    booking = BookingFactory()

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Performance Sold Out: {booking.performance.production.name}",
                title_icon="rocket",
            ),
            Image(src=testTrashImage),
            Paragraph(
                message=f"The performance of <strong>{booking.performance.production.name}</strong> on <strong>{booking.performance.start.strftime('%d/%m/%Y %I:%M %p')}</strong> is now sold out. Congratulations!",
                html_safe=True,
            ),
            Paragraph(
                message=f"Break a leg!",
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "performance_sold_out_email")


@pytest.mark.django_db
def test_notify_admins_of_comp_booking_email():

    booking = BookingFactory()

    authorising_user = UserFactory()

    test_mail = MailComposer.blank(
        [
            Heading(
                title=f"Comp Booking Made: {booking.performance.production.name}",
                title_icon="ticket",
            ),
            Image(src=testTrashImage),
            Paragraph(
                message=f"A comp booking has been made for <strong>{booking.performance.production.name}</strong> on <strong>{booking.performance.start.strftime('%d/%m/%Y %I:%M %p')}</strong>.",
                html_safe=True,
            ),
            Paragraph(
                message=f"This booking was authorised by <strong>{authorising_user.first_name} {authorising_user.last_name}</strong> (<em>{authorising_user.email}</em>).",
                html_safe=True,
            ),
            Paragraph(
                message=f"If there are any issues, or the booking was made in error, please contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>.",
                html_safe=True,
            ),
            Button(
                f"/administration/productions/{booking.performance.production.slug}/bookings/{booking.reference}",
                "View Booking Details",
            ),
            Closer(),
        ]
    )

    write_files(test_mail, "comp_booking_made_email")
