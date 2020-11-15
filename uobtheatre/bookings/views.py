from rest_framework import mixins, generics
from rest_framework.permissions import AllowAny, IsAuthenticated 

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import UserBookingGetSerialiser


class BookingList(generics.ListAPIView):
    """
    API endpoint that allows Users to see thier bookings.
    """

    # permission_classes = (IsAuthenticated,)
    serializer_class = UserBookingGetSerialiser

    def get_queryset(self):
        user = self.request.user

        return Booking.objects.filter(user=user)