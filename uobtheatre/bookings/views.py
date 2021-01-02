from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import BookingSerialiser, CreateBookingSerialiser
from uobtheatre.utils.models import ReadWriteSerializerMixin


class BookingViewSet(ReadWriteSerializerMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows Users to see thier bookings.
    """

    permission_classes = (IsAuthenticated,)
    read_serializer_class = BookingSerialiser
    write_serializer_class = CreateBookingSerialiser

    def get_queryset(self):
        user = self.request.user
        return Booking.objects.filter(user=user)

    def get_serializer_context(self):
        context = super(BookingViewSet, self).get_serializer_context()
        context.update({"user": self.request.user})
        return context
