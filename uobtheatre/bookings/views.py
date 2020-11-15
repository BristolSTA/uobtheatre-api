from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import UserBookingGetSerialiser


class UserBookingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Users to see thier bookings.
    """

    queryset = Booking.objects.all()
    serializer_class = UserBookingGetSerialiser
