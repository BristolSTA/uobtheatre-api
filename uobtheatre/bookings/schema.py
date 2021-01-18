import graphene
from graphene_django_extras import DjangoFilterListField, DjangoObjectType

from uobtheatre.bookings.models import Booking, ConcessionType


class ConcessionTypeType(DjangoObjectType):
    class Meta:
        model = ConcessionType


class BookingType(DjangoObjectType):
    class Meta:
        model = Booking


class Query(graphene.ObjectType):
    bookings = DjangoFilterListField(BookingType)

    def resolve_bookings(self, info):
        if not info.context.user.is_authentiacted:
            return Booking.objects.none()
        else:
            return Booking.objects.filter(user=info.context.user)
