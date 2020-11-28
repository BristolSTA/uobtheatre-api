import pytest
import uuid

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import (
    BookingSerialiser,
    CreateBookingSerialiser,
    CreateSeatBookingSerializer,
)
from uobtheatre.bookings.test.factories import BookingFactory, ConsessionTypeFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


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


@pytest.mark.django_db
def test_create_booking_serializer_obj_to_json(date_format_2):
    booking = BookingFactory()
    data = Booking.objects.first()
    serialized_booking = CreateBookingSerialiser(data)

    seat_bookings = [
        {
            "seat_group": seat_booking.seat_group.id,
            "consession_type": seat_booking.consession_type.name,
        }
        for seat_booking in booking.seat_bookings.all()
    ]

    assert serialized_booking.data == {
        "user_id": str(booking.user.id),
        "seat_bookings": seat_bookings,
        "performance_id": booking.performance.id,
    }


@pytest.mark.django_db
def test_create_booking_serializer_json_to_obj(date_format_2):
    user = UserFactory()
    performance = PerformanceFactory()
    seat_group = SeatGroupFactory()
    consession_type = ConsessionTypeFactory()
    data = {
        "user_id": user.id,
        "performance_id": performance.id,
        "seat_bookings": [
            {
                "seat_group_id": seat_group.id,
                "consession_type_id": consession_type.id,
            },
        ],
    }

    serialized_booking = CreateBookingSerialiser(data=data)
    assert serialized_booking.is_valid()

    serialized_booking.save()

    created_booking = Booking.objects.first()
    serialized_booking = CreateBookingSerialiser(created_booking)

    assert serialized_booking.data == data


@pytest.mark.skip(reason="Need to write this")
def test_create_seat_booking_serializer(date_format_2):
    seat_booking = SeatBooking()
    data = SeatBooking.objects.first()
    serialized_booking = CreateSeatBookingSerialiser(data)
