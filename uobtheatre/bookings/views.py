from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import (
    BookingListSerialiser,
    BookingSerialiser,
    CreateBookingSerialiser,
)
from uobtheatre.utils.views import ReadWriteSerializerMixin


class BookingViewSet(
    ReadWriteSerializerMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    API endpoint that allows Users to see thier bookings.
    """

    permission_classes = (IsAuthenticated,)
    list_read_serializer_class = BookingListSerialiser  # type: ignore
    detail_read_serializer_class = BookingSerialiser  # type: ignore
    write_serializer_class = CreateBookingSerialiser  # type: ignore

    filter_fields = [
        "status",
        "booking_reference",
        "performance_id",
    ]

    def get_queryset(self):
        user = self.request.user
        return Booking.objects.filter(user=user)

    def get_serializer_context(self):
        context = super(BookingViewSet, self).get_serializer_context()
        context.update({"user": self.request.user})
        return context
