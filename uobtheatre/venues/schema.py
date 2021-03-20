import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.fields import DjangoConnectionField
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.addresses.schema import AddressNode  # noqa
from uobtheatre.productions.schema import ProductionNode
from uobtheatre.venues.models import Seat, SeatGroup, Venue


class SeatGroupNode(DjangoObjectType):
    class Meta:
        model = SeatGroup
        interfaces = (relay.Node,)
        exclude = ("performance_set", "performanceseatgroup_set", "discount_set")


class SeatNode(DjangoObjectType):
    class Meta:
        model = Seat
        interfaces = (relay.Node,)


class VenueNode(DjangoObjectType):
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
    venue = graphene.Field(VenueNode, slug=graphene.String(required=True))

    def resolve_venue(self, info, slug):
        return Venue.objects.get(slug=slug)
