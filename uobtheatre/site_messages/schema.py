import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.site_messages.models import Message
from uobtheatre.users.abilities import PermissionsMixin
from uobtheatre.utils.filters import FilterSet
from uobtheatre.utils.schema import UserPermissionFilterMixin, IdInputField

class SiteMessageFilterSet(FilterSet, UserPermissionFilterMixin):
    class Meta:
        fields = ("id", "message")
        model = Message

class SiteMessageNode(PermissionsMixin, DjangoObjectType):
    event_duration = graphene.Int()

    def resolve_event_duration(self, info):
        return self.duration.total_seconds() // 60

    class Meta:
        model = Message
        interfaces = (relay.Node,)
        filterset_class = SiteMessageFilterSet
        fields = (
            "id",
            "message",
            "active",
            "indefinite_override",
            "display_start",
            "event_start",
            "event_end",
            "type",
            "creator",
            "dismissal_policy"
        )

class Query(graphene.ObjectType):
    site_messages = DjangoFilterConnectionField(SiteMessageNode)
    site_message = graphene.Field(SiteMessageNode, id=IdInputField(required=True))

    def resolve_site_message(self, _, id):
        try:
            return Message.objects.get(id=id)
        except Message.DoesNotExist:
            return None
