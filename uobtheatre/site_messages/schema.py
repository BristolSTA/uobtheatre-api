import graphene
from graphene_django import DjangoObjectType

from uobtheatre.site_messages.models import Message

class SiteMessageNode(DjangoObjectType):
    class Meta:
        model = Message

class Query(graphene.ObjectType):
    site_messages = graphene.List(SiteMessageNode)

    def resolve_messages(self, _):
        return Message.objects.all()