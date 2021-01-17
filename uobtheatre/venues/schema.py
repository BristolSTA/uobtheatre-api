import graphene
from graphene_django import DjangoObjectType

from uobtheatre.venues.models import SeatGroup, Venue


class SeatGroupType(DjangoObjectType):
    class Meta:
        model = SeatGroup


class VenueType(DjangoObjectType):
    class Meta:
        model = Venue


class Query(graphene.ObjectType):
    venues = graphene.List(VenueType)

    def resolve_venues(self, info, **kwargs):
        return Venue.objects.all()
