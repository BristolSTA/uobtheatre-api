import graphene
from django.forms import CharField

from uobtheatre.site_messages.models import Message
from uobtheatre.users.models import User
from uobtheatre.utils.forms import MutationForm


class SiteMessageForm(MutationForm):
    """Form for creating/updating a site message"""

    def clean(self):
        """Validate and clean form data"""
        if not self.instance.user_id:
            # If the instance has no creator, the current user is the creator
            self.instance.user = self.user

    class Meta:
        model = Message
        fields = [
            "message",
            "active",
            "indefinite_override",
            "display_start",
            "event_start",
            "event_end",
            "type",
            "dismissal_policy",
            "display_location",
            "title",
        ]
