import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.images.schema import ImageNode  # noqa
from uobtheatre.societies.models import Society
from uobtheatre.users.abilities import PermissionsMixin
from uobtheatre.utils.filters import FilterSet
from uobtheatre.utils.schema import UserPermissionFilterMixin


class SocietyFilterSet(FilterSet, UserPermissionFilterMixin):
    class Meta:
        fields = ("id", "name", "slug")
        model = Society


class SocietyNode(PermissionsMixin, DjangoObjectType):
    class Meta:
        model = Society
        interfaces = (relay.Node,)
        filterset_class = SocietyFilterSet
        fields = (
            "created_at",
            "updated_at",
            "name",
            "slug",
            "description",
            "logo",
            "banner",
            "website",
            "contact",
            "members",
            "productions",
            "permissions",
        )


class Query(graphene.ObjectType):
    societies = DjangoFilterConnectionField(SocietyNode)
    society = graphene.Field(SocietyNode, slug=graphene.String(required=True))

    def resolve_society(self, _, slug):
        try:
            return Society.objects.get(slug=slug)
        except Society.DoesNotExist:
            return None
