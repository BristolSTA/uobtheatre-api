import graphene
from django.forms import CharField

from uobtheatre.site_messages.models import Message
from uobtheatre.users.models import User
from uobtheatre.utils.forms import MutationForm


class SiteMessageForm(MutationForm):
    """Form for creating/updating a site message"""

    user_email = CharField(required=False)

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
            "creator",
            "dismissal_policy",
        ]
