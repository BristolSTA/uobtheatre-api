import graphene
from graphene_django import DjangoObjectType

from uobtheatre.venues.models import Venue


class VenueType(DjangoObjectType):
    class Meta:
        model = Venue


class Query(graphene.ObjectType):
    venues = graphene.List(VenueType)

    def resolve_venues(self, info, **kwargs):
        return Venue.objects.all()
