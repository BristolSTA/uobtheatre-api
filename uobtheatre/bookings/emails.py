from typing import TYPE_CHECKING, Optional

from uobtheatre.mail.composer import MailComposer
from uobtheatre.payments.models import Transaction
from uobtheatre.utils.permissions import get_users_with_perm

if TYPE_CHECKING:
    from uobtheatre.bookings.models import Booking


def send_booking_confirmation_email(
    booking: "Booking", payment: Optional[Transaction] = None
):
    """
    Send email confirmation which includes a link to the booking.
    """
    composer = MailComposer()

    composer.line(
        "Your booking to %s has been confirmed!" % booking.performance.production.name
    )

    if booking.performance.production.featured_image:
        composer.image(booking.performance.production.featured_image.file.url)

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
    if payment:
        composer.heading("Payment Information").line(
            f"{payment.value_currency} paid ({payment.provider.description}{' - ID ' + payment.provider_transaction_id if payment.provider_transaction_id else '' })"
        )

    composer.line(
        "If you have any accessability concerns, or otherwise need help, please contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>."
    )

    composer.send("Your booking is confirmed!", booking.user.email)


def send_booking_accessibility_info_email(
    booking: "Booking",
):
    """Sends an email to the production contact email, and to those with view sales and bookings permissions for a production, notifying them of a booking that has been amde with accessibility information"""

    emails_to_notify = [booking.performance.production.contact_email] + list(
        get_users_with_perm("productions.view_bookings", booking.performance.production)
        .all()
        .values_list("email", flat=True)
    )

    mail = (
        MailComposer()
        .greeting()
        .line(
            f"A patron has <strong>added</strong> accessibility information in their booking for {booking.performance}. Please review the booking for further information and see if any action is required. Ensure you liase with your venue and front of house teams about this: do not assume that they are aware of this information. Please contact the patron directly if you need to discuss this information with them."
        )
        .action(
            f"/administration/productions/{booking.performance.production.slug}/bookings/{booking.reference}",
            "View Booking Details",
        )
        .line(
            "Please remember that accessibility information is sensitive and should be treated with care. Only those who need to know should be informed of this information."
        )
    )
    for email in emails_to_notify:
        mail.send(
            f"Accessibility alert for {booking.performance.production.name}", email
        )


def send_booking_accessibility_removed_email(
    booking: "Booking",
):
    """
    Sends an email to the production contact email and to those with view sales and bookings permissions for a production,
    notifying that a previously accessible booking has had its accessibility information removed.
    """

    emails_to_notify = [booking.performance.production.contact_email] + list(
        get_users_with_perm("productions.view_bookings", booking.performance.production)
        .all()
        .values_list("email", flat=True)
    )

    mail = (
        MailComposer()
        .greeting()
        .line(
            f"A patron has <strong>removed</strong> their accessibility information in their booking for {booking.performance}. You may still view the previously entered accessibility information for your reference. Ensure you liase with your venue and front of house teams about this: do not assume that they are aware of this information. Please contact the patron directly if you need to clarify this information with them."
        )
        .action(
            f"/administration/productions/{booking.performance.production.slug}/bookings/{booking.reference}",
            "View Booking Details",
        )
        .line(
            "Please remember that accessibility information is sensitive and should be treated with care. Only those who need to know should be informed of this information."
        )
    )
    for email in emails_to_notify:
        mail.send(
            f"Accessibility alert for {booking.performance.production.name}", email
        )


def send_booking_accessibility_updated_email(
    booking: "Booking",
):
    """
    Sends an email to the production contact email and to those with view sales and bookings permissions for a production,
    notifying that a booking has had its accessibility information updated.
    """

    emails_to_notify = [booking.performance.production.contact_email] + list(
        get_users_with_perm("productions.view_bookings", booking.performance.production)
        .all()
        .values_list("email", flat=True)
    )

    mail = (
        MailComposer()
        .greeting()
        .line(
            f"A patron has <strong>updated</strong> their accessibility information in their booking for {booking.performance}. You may still view the previously entered accessibility information for your reference. Ensure you liase with your venue and front of house teams about this: do not assume that they are aware of this information. Please contact the patron directly if you need to clarify this information with them."
        )
        .action(
            f"/administration/productions/{booking.performance.production.slug}/bookings/{booking.reference}",
            "View Booking Details",
        )
        .line(
            "Please remember that accessibility information is sensitive and should be treated with care. Only those who need to know should be informed of this information."
        )
    )
    for email in emails_to_notify:
        mail.send(
            f"Accessibility alert for {booking.performance.production.name}", email
        )
