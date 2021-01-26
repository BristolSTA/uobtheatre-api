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

    class Meta:
        model = Society
        interfaces = (relay.Node,)
        filter_fields = {
            "id": ("exact",),
            "name": ("exact",),
        }


class Query(graphene.ObjectType):
    societies = DjangoFilterConnectionField(SocietyNode)
