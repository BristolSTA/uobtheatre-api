import graphene

from uobtheatre.site_messages.forms import SiteMessageForm
from uobtheatre.site_messages.models import Message
from uobtheatre.site_messages.schema import SiteMessageNode
from uobtheatre.utils.schema import AuthRequiredMixin, SafeFormMutation


class SiteMessageMutation(SafeFormMutation, AuthRequiredMixin):
    """
    Mutation to create/edit a site message.
    """

    site_message = graphene.Field(SiteMessageNode)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        super().authorize_request(root, info, **inputs)

    class Meta:
        form_class = SiteMessageForm
        createAbility = "site_messages.add_message"


class Mutation(graphene.ObjectType):
    site_message = SiteMessageMutation.Field()
