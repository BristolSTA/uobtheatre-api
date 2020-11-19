from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import UserBookingGetSerialiser


class UserBookingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Users to see thier bookings.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = UserBookingGetSerialiser

    def get_queryset(self):
        user = self.request.user

        return Booking.objects.filter(user=user)
