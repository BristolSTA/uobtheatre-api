import datetime
from typing import Optional

from django.db import models
from django.utils import timezone
from graphql_relay.node.node import to_global_id

from uobtheatre.users.models import User
from uobtheatre.utils.models import BaseModel
from uobtheatre.utils.validators import RequiredFieldsValidator


class Message(BaseModel):
    """The model for a site-wide message."""

    message = models.TextField(
        help_text="The message displayed in the body of the banner."
    )  # The message displayed in the body of the banner.
    active = models.BooleanField(
        default=True,
        help_text="Whether the message is active. Inactive messages will not be displayed, even if display_start is in the past.",
    )  # Whether the message is active. Inactive messages will not be displayed, even if display_start is in the past.

    # Overrides the event_end time to be indefinite. If True,
    # the message will be displayed without a Date/Time/Duration if
    # it is ongoing, and without a duration if it is in the future.
    # In addition, it will continue to display even after the event_end
    # until either active or indefinite_override is set to False.
    indefinite_override = models.BooleanField(
        default=False,
        help_text="If True, the message will be displayed without a Date/Time/Duration if it is ongoing, and without a duration if it is in the future. In addition, it will continue to display even after the event_end until either active or indefinite_override is set to False.",
    )

    display_start = models.DateTimeField(
        null=True,
        help_text="When the message should start being displayed on the website. If null, the message will be displayed immediately.",
    )  # When the message should start being displayed on the website. If null, the message will be displayed immediately.
    event_start = models.DateTimeField(
        help_text="When the banner shows the event will begin (date and time)."
    )  # When the banner shows the event will begin (date and time)
    event_end = models.DateTimeField(
        help_text="When the event will end. Used both to calculate duration and to know when to stop displaying the message."
    )  # When the event will end. Used both to calculate duration and to know when to stop displaying the message.

    # The user that created the message
    creator = models.ForeignKey(
        User, on_delete=models.RESTRICT, related_name="created_site_messages"
    )

    class Type(models.TextChoices):
        """The type of message, which informs how it is displayed."""

        MAINTENANCE = (
            "MAINTENANCE",
            "Maintenance",
        )  # Message is for maintenance purposes (displayed in yellow if upcoming, red if ongoing)
        INFORMATION = (
            "INFORMATION",
            "Information",
        )  # Message is information (displayed in yellow information text)
        ALERT = "ALERT", "Alert"  # Message is an urgent alert (displayed in red text)

    type = models.CharField(
        max_length=11,
        choices=Type.choices,
        default=Type.MAINTENANCE,
        help_text="The type of message, which informs how it is displayed. Maintenance messages are displayed in yellow if upcoming, red if ongoing. Information messages are displayed in yellow information text. Alert messages are displayed in red text.",
    )

    class Policy(models.TextChoices):
        """The policy for a message's dismissal."""

        DEFAULT = (
            "DEFAULT",
            "Dismissable (Default)",
        )  # Message can be dismissed, and dismissal is stored in the cache until the event is over
        SINGLE = (
            "SINGLE",
            "Single-Session Only",
        )  # Message can be dismissed, but dismissal is not cached
        BANNED = "BANNED", "Prevented"  # Cannot be dismissed by the user

    dismissal_policy = models.CharField(
        max_length=7,
        choices=Policy.choices,
        default=Policy.DEFAULT,
        help_text="The policy for a message's dismissal. By default messages are dismissable, and this choice is stored in the cache until the event is over. Single-Session Only messages can be dismissed, but dismissal is not cached. Prevented messages cannot be dismissed by the user.",
    )

    @property
    def duration(self) -> datetime.timedelta:
        """The event duration.

        Duration is measured from start time to end time.

        Returns:
            timedelta: Timedelta between start and end of event.
        """
        return self.event_end - self.event_start

    @property
    def to_display(self) -> bool:
        """Whether the message should currently be displayed.

        Messages are displayed if they are active, and either the display_start is in the past or null,

        Returns:
            bool: Whether the message should be displayed.
        """
        return (
            self.active
            and (not (self.display_start) or self.display_start < timezone.now())
            and (self.indefinite_override or self.event_end > timezone.now())
        )

    VALIDATOR = RequiredFieldsValidator(
        [
            "message",
            "active",
            "event_start",
            "event_end",
            "creator",
            "type",
            "dismissal_policy",
        ]
    )

    def __str__(self):
        return f"Site {self.type.title()} (Event {self.event_start} until {self.event_start})"

    class Meta:
        verbose_name = "Site Message"
        verbose_name_plural = "Site Messages"
