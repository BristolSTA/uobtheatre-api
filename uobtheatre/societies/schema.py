import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.images.schema import ImageNode  # noqa
from uobtheatre.societies.models import Society
from uobtheatre.users.abilities import PermissionsMixin


class SocietyNode(PermissionsMixin, DjangoObjectType):
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

    def resolve_society(self, _, slug):
        try:
            return Society.objects.get(slug=slug)
        except Society.DoesNotExist:
            return None
