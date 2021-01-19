import graphene
from graphene_django_extras import (
    DjangoFilterListField,
    DjangoListObjectType,
    DjangoObjectType,
)

from uobtheatre.bookings.models import Booking, ConcessionType


class ConcessionTypeType(DjangoObjectType):
    class Meta:
        model = ConcessionType


class BookingListType(DjangoListObjectType):
    class Meta:
        model = Booking
        queryset = Booking.obj


class Query(graphene.ObjectType):
    bookings = DjangoFilterListField(BookingListType)

    def resolve_bookings(self, info):
        print("Resolving bookings")
        if not info.context.user.is_authentiacted:
            return Booking.objects.none()
        else:
            return Booking.objects.filter(user=info.context.user)
