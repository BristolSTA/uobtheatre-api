from typing import List, Optional

from uobtheatre.mail.composer import MailComposer
from uobtheatre.productions.models import Performance, Production
from uobtheatre.users.models import User
from uobtheatre.utils.lang import pluralize


def send_production_approved_email(user: User, production: Production):
    """Send a production approval email"""
    mail = MailComposer()
    mail.greeting(user).line(
        f"Your production '{production.name}' has been approved."
    ).line(
        "You may now create complimentry bookings and, when ready, make it public, by going to the production control panel."
    ).action(
        f"/administration/productions/{production.slug}",
        "Go To Production Control Panel",
    ).send(
        f"{production.name} has been approved", user.email
    )


def send_production_needs_changes_email(
    user: User, production: Production, message: Optional[str] = None
):
    """Send a production needs change email"""
    mail = MailComposer()
    mail.greeting(user).line(
        f"We have reviewed your production ({production.name}), and some changes need to be made before we can approve it."
    )

    if message:
        mail.line(f"Review Comment: '{message}'")
    mail.line(
        "You can go back to the production control panel to make the required changes."
    ).action(
        f"/administration/productions/{production.slug}",
        "Go To Production Control Panel",
    ).line(
        "If you need any help, please contact us at support@uobtheatre.com"
    ).send(
        f"{production.name} needs changes", user.email
    )


def send_production_ready_for_review_email(user: User, production: Production):
    """Send a production ready for review email"""
    mail = MailComposer()
    mail.greeting(user).line(
        f"'{production.name}' has been submitted for review. Please head to the admin control panel, verify the production's details and listing, and either approve or reject."
    ).action(
        f"/administration/productions/{production.slug}",
        "Go To Production Control Panel",
    ).send(
        f"{production.name} is ready for approval", user.email
    )


def performances_refunded_email(
    authorizing_user: User,
    performances: List[Performance],
):
    """Generate an email detailing performance refund statistics

    Args:
        authorizing_user (User): The user authorising the refunds
        performances (List[Performance]): The performances refunded

    Returns:
        MailComposer: Mail instance
    """
    mail = (
        MailComposer()
        .greeting()
        .line(
            f"Refund(s) have been initiated for the following {pluralize('performance', performances)}:"
        )
        .line(
            ", ".join(
                f"{performance.pk} | {str(performance)}" for performance in performances
            )
        )
        .line(
            f"This action was requested by {authorizing_user.full_name} ({authorizing_user.email})"
        )
        .line("For more info please check the admin panel.")
    )
    return mail
