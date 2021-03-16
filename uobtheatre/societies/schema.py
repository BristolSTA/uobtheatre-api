import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.societies.models import Society
from uobtheatre.utils.schema import (
    GrapheneImageField,
    GrapheneImageFieldNode,
    GrapheneImageMixin,
)


class SocietyNode(GrapheneImageMixin, DjangoObjectType):
    logo = GrapheneImageField(GrapheneImageFieldNode)
    banner = GrapheneImageField(GrapheneImageFieldNode)

    class Meta:
        model = Society
        interfaces = (relay.Node,)
        filter_fields = {
            "id": ("exact",),
            "name": ("exact",),
            "slug": ("exact",),
        }


class Query(graphene.ObjectType):
    societies = DjangoFilterConnectionField(SocietyNode)
    society = graphene.Field(SocietyNode, slug=graphene.String(required=True))

    def resolve_society(self, info, slug):
        return Society.objects.get(slug=slug)
