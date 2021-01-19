import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.venues.models import SeatGroup, Venue


class SeatGroupNode(DjangoObjectType):
    class Meta:
        model = SeatGroup
        interfaces = (relay.Node,)


class VenueNode(DjangoObjectType):
    class Meta:
        model = Venue
        interfaces = (relay.Node,)
        filter_fields = {}


class Query(graphene.ObjectType):
    venues = DjangoFilterConnectionField(VenueNode)

    def resolve_venues(self, info, **kwargs):
        return Venue.objects.all()
