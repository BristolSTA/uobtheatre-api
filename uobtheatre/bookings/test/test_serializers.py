import pytest
import uuid

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import (
    BookingSerialiser,
    CreateBookingSerialiser,
    CreateSeatBookingSerializer,
)
from uobtheatre.bookings.test.factories import BookingFactory


@pytest.mark.django_db
def test_booking_serializer(date_format_2):
    booking = BookingFactory()
    data = Booking.objects.first()
    serialized_booking = BookingSerialiser(data)

    performance = {
        "id": booking.performance.id,
        "production_id": booking.performance.production.id,
        "venue": {
            "id": booking.performance.venue.id,
            "name": booking.performance.venue.name,
        },
        "extra_information": booking.performance.extra_information,
        "start": booking.performance.start.strftime(date_format_2),
        "end": booking.performance.end.strftime(date_format_2),
    }

    assert serialized_booking.data == {
        "id": booking.id,
        "user_id": str(booking.user.id),
        "booking_reference": str(booking.booking_reference),
        "performance": performance,
    }


@pytest.mark.skip(reason="Need to write this")
@pytest.mark.django_db
def test_create_booking_serializer(date_format_2):
    booking = BookingFactory()
    data = Booking.objects.first()
    serialized_booking = CreateBookingSerialiser(data)


@pytest.mark.skip(reason="Need to write this")
def test_create_seat_booking_serializer(date_format_2):
    seat_booking = SeatBooking()
    data = SeatBooking.objects.first()
    serialized_booking = CreateSeatBookingSerialiser(data)
