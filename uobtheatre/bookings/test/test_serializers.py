import uuid

import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import (BookingSerialiser,
                                             CreateBookingSerialiser,
                                             CreateSeatBookingSerializer)
from uobtheatre.bookings.test.factories import (BookingFactory,
                                                ConsessionTypeFactory)
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_booking_serializer(date_format):
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
        "start": booking.performance.start.strftime(date_format),
        "end": booking.performance.end.strftime(date_format),
    }

    assert serialized_booking.data == {
        "id": booking.id,
        "user_id": str(booking.user.id),
        "booking_reference": str(booking.booking_reference),
        "performance": performance,
    }


@pytest.mark.django_db
def test_create_booking_serializer():
    user = UserFactory()
    performance = PerformanceFactory()
    seat_group = SeatGroupFactory()
    consession_type = ConsessionTypeFactory()
    data = {
        "performance_id": performance.id,
        "seat_bookings": [
            {
                "seat_group_id": seat_group.id,
                "consession_type_id": consession_type.id,
            },
        ],
    }

    serialized_booking = CreateBookingSerialiser(data=data, context={"user": user})
    assert serialized_booking.is_valid()

    serialized_booking.save()

    created_booking = Booking.objects.first()
    serialized_booking = CreateBookingSerialiser(created_booking)

    assert serialized_booking.data == data
    assert str(created_booking.user.id) == str(user.id)


@pytest.mark.django_db
def test_create_booking_serializer_validation():
    user = UserFactory()
    performance = PerformanceFactory()
    seat_group = SeatGroupFactory()
    consession_type = ConsessionTypeFactory()

    # Check performance is required to create booking
    data = {
        "seat_bookings": [
            {
                "seat_group_id": seat_group.id,
                "consession_type_id": consession_type.id,
            },
        ],
    }

    serialized_booking = CreateBookingSerialiser(data=data, context={"user": user})
    assert not serialized_booking.is_valid()

    # Assert seat group is required for each seat booking
    data = {
        "performance_id": performance.id,
        "seat_bookings": [
            {
                "consession_type_id": consession_type.id,
            },
        ],
    }

    serialized_booking = CreateBookingSerialiser(data=data, context={"user": user})
    assert not serialized_booking.is_valid()

    # Check consession type is not required (default to adult)
    # TODO write test to check default to adult
    data = {
        "performance_id": performance.id,
        "seat_bookings": [
            {
                "seat_group_id": seat_group.id,
            },
        ],
    }

    serialized_booking = CreateBookingSerialiser(data=data, context={"user": user})
    assert serialized_booking.is_valid()

    # Check seat booking is not required
    data = {
        "performance_id": performance.id,
    }

    serialized_booking = CreateBookingSerialiser(data=data, context={"user": user})
    assert serialized_booking.is_valid()

    # Check booking with all data is valid
    data = {
        "performance_id": performance.id,
        "seat_bookings": [
            {
                "seat_group_id": seat_group.id,
                "consession_type_id": consession_type.id,
            },
        ],
    }

    serialized_booking = CreateBookingSerialiser(data=data, context={"user": user})
    assert serialized_booking.is_valid()


@pytest.mark.skip(reason="Need to write this")
def test_create_seat_booking_serializer():
    seat_booking = SeatBooking()
    data = SeatBooking.objects.first()
    serialized_booking = CreateSeatBookingSerialiser(data)
