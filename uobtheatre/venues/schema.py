import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.fields import DjangoConnectionField
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.addresses.schema import AddressNode  # noqa
from uobtheatre.productions.schema import ProductionNode
from uobtheatre.utils.schema import (
    GrapheneImageField,
    GrapheneImageFieldNode,
    GrapheneImageMixin,
)
from uobtheatre.venues.models import SeatGroup, Venue


class SeatGroupNode(DjangoObjectType):
    class Meta:
        model = SeatGroup
        interfaces = (relay.Node,)


class VenueNode(GrapheneImageMixin, DjangoObjectType):
    image = GrapheneImageField(GrapheneImageFieldNode)
    productions = DjangoConnectionField(ProductionNode)

    def resolve_productions(self, info):
        return self.get_productions()

    class Meta:
        model = Venue
        interfaces = (relay.Node,)
        filter_fields = {
            "id": ("exact",),
            "name": ("exact",),
            "slug": ("exact",),
        }


class Query(graphene.ObjectType):
    venues = DjangoFilterConnectionField(VenueNode)

    def resolve_venues(self, info, **kwargs):
        return Venue.objects.all()
