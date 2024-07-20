import datetime
from typing import Optional

from django.db import models
from django.utils import timezone

from uobtheatre.users.models import User
from uobtheatre.utils.validators import RequiredFieldsValidator


class Message(models.Model):
    """The model for a site-wide message."""

    message = models.TextField()  # The message displayed in the body of the banner
    active = models.BooleanField(
        default=True
    )  # Whether the message is active. Inactive messages will not be displayed, even if display_start is in the past

    # Overrides the event_end time to be indefinite. If this is true,
    # the message will be displayed without a Date/Time/Duration if
    # it is ongoing, and without a duration if it is in the future.
    # In addition, it will continue to display even after the event_end
    # until either active or indefinite_override is set to False.
    indefinite_override = models.BooleanField(default=False)

    display_start = models.DateTimeField(
        null=True
    )  # When the message should start being displayed on the website. If null, the message will be displayed immediately
    event_start = (
        models.DateTimeField()
    )  # When the banner shows the event will begin (date and time)
    event_end = (
        models.DateTimeField()
    )  # When the event will end. Used both to calculate duration and to know when to stop displaying the message

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
        max_length=11, choices=Type.choices, default=Type.MAINTENANCE
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
        max_length=7, choices=Policy.choices, default=Policy.DEFAULT
    )

    @property
    def duration(self) -> datetime.timedelta:
        """The event duration.

        Duration is measured from start time to end time.

        Returns:
            timedelta: Timedelta between start and end of event.
        """
        return self.event_start - self.event_end

    @property
    def to_display(self) -> bool:
        """Whether the message should currently be displayed.
        
        Messages are displayed if they are active, and either the display_start is in the past or null,

        Returns:
            bool: Whether the message should be displayed.
        """
        return (
            self.active and
            (not (self.display_start) or self.display_start < timezone.now()) and
            (self.indefinite_override or self.event_end > timezone.now())
        )

    VALIDATOR = RequiredFieldsValidator(
        [
            "message",
            "active",
            "display_start",
            "event_start",
            "event_end",
            "creator",
            "type",
            "dismissal_policy",
        ]
    )
