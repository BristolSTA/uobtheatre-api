import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.bookings.models import Booking, ConcessionType


class ConcessionTypeNode(DjangoObjectType):
    class Meta:
        model = ConcessionType
        interfaces = (relay.Node,)


class BookingNode(DjangoObjectType):
    class Meta:
        model = Booking
        interfaces = (relay.Node,)
        filter_fields = {}


class Query(graphene.ObjectType):
    bookings = DjangoFilterConnectionField(BookingNode)

    def resolve_bookings(self, info):
        # If the user is not authenticated then return none
        if not info.context.user.is_authenticated:
            return Booking.objects.none()
        # Otherwise return only the user's bookings
        return Booking.objects.filter(user=info.context.user)
