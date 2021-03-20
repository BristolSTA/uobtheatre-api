import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.images.schema import ImageNode  # noqa
from uobtheatre.societies.models import Society


class SocietyNode(DjangoObjectType):
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
