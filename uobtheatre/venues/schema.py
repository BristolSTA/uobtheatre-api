import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.addresses.schema import AddressNode  # noqa
from uobtheatre.images.schema import ImageNode  # noqa
from uobtheatre.venues.models import Seat, SeatGroup, Venue


class SeatGroupNode(DjangoObjectType):
    class Meta:
        model = SeatGroup
        interfaces = (relay.Node,)
        fields = ("name", "description", "venue", "capacity", "is_internal")


class SeatNode(DjangoObjectType):
    class Meta:
        model = Seat
        interfaces = (relay.Node,)
        fields = ("row", "number")


class VenueNode(DjangoObjectType):
    productions = DjangoFilterConnectionField(
        "uobtheatre.productions.schema.ProductionNode"
    )

    def resolve_productions(self, info, **kwargs):
        from uobtheatre.productions.schema import ProductionFilter

        return ProductionFilter(kwargs, self.get_productions()).qs

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

    def resolve_venue(self, _, slug):
        try:
            return Venue.objects.get(slug=slug)
        except Venue.DoesNotExist:
            return None
