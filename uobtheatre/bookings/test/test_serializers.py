import uuid

import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.serializers import (
    BookingSerialiser,
    CreateBookingSerialiser,
    CreateTicketSerializer,
    DiscountSerializer,
    ValueMiscCostSerializer,
    PercentageMiscCostSerializer,
)
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
    ValueMiscCostFactory,
    PercentageMiscCostFactory,
    PerformanceSeatingFactory,
)
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
            "slug": booking.performance.venue.slug,
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
    concession_type = ConcessionTypeFactory()
    data = {
        "performance_id": performance.id,
        "tickets": [
            {
                "seat_group_id": seat_group.id,
                "concession_type_id": concession_type.id,
            },
        ],
    }

    serialized_booking = CreateBookingSerialiser(data=data, context={"user": user})
    assert serialized_booking.is_valid()

    serialized_booking.save()

    created_booking = Booking.objects.first()
    serialized_booking = CreateBookingSerialiser(created_booking)

    data["id"] = created_booking.id
    assert serialized_booking.data == data
    assert str(created_booking.user.id) == str(user.id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, is_valid",
    [
        # Check performance is required to create booking
        (
            {
                "tickets": [
                    {
                        "seat_group_id": 1,
                        "concession_type_id": 1,
                    },
                ],
            },
            False,
        ),
        # Assert seat group is required for each seat booking
        (
            {
                "performance_id": 1,
                "tickets": [
                    {
                        "concession_type_id": 1,
                    },
                ],
            },
            False,
        ),
        # Check concession type is not required (default to adult)
        # TODO write test to check default to adult
        (
            {
                "performance_id": 1,
                "tickets": [
                    {
                        "seat_group_id": 1,
                    },
                ],
            },
            True,
        ),
        # Check seat booking is not required
        (
            {
                "performance_id": 1,
            },
            True,
        ),
        (
            # Check booking with all data is valid
            {
                "performance_id": 1,
                "tickets": [
                    {
                        "seat_group_id": 1,
                        "concession_type_id": 1,
                    },
                ],
            },
            True,
        ),
    ],
)
def test_create_booking_serializer_validation(data, is_valid):
    user = UserFactory(id=1)
    performance = PerformanceFactory(id=1)
    seat_group = SeatGroupFactory(id=1)
    concession_type = ConcessionTypeFactory(id=1)

    serialized_booking = CreateBookingSerialiser(data=data, context={"user": user})
    assert serialized_booking.is_valid() == is_valid


@pytest.mark.skip(reason="Need to write this")
def test_create_seat_booking_serializer():
    seat_booking = SeatBooking()
    data = SeatBooking.objects.first()
    serialized_booking = CreateSeatBookingSerialiser(data)


@pytest.mark.django_db
def test_discount_serializer():
    discount = DiscountFactory()
    requirement = DiscountRequirementFactory(discount=discount)

    serialized_discount = DiscountSerializer(discount)

    requirements = [
        {
            "number": requirement.number,
            "concession_type": {
                "id": requirement.concession_type.id,
                "name": requirement.concession_type.name,
                "description": requirement.concession_type.description,
            },
        }
    ]

    assert serialized_discount.data == {
        "name": discount.name,
        "discount": discount.discount,
        "seat_group": discount.seat_group,
        "discount_requirements": requirements,
    }


@pytest.mark.django_db
def test_value_misc_cost_serializer():
    value_misc_cost = ValueMiscCostFactory()
    serialized_misc_cost = ValueMiscCostSerializer(value_misc_cost)

    assert serialized_misc_cost.data == {
        "name": value_misc_cost.name,
        "description": value_misc_cost.description,
        "value": value_misc_cost.value,
    }


@pytest.mark.django_db
def test_percentage_misc_cost_serializer():
    percentage_misc_cost = PercentageMiscCostFactory()
    serialized_misc_cost = PercentageMiscCostSerializer(percentage_misc_cost)

    # Test with no booking supplied
    expected = {
        "name": percentage_misc_cost.name,
        "description": percentage_misc_cost.description,
        "percentage": percentage_misc_cost.percentage,
        "value": None,
    }
    assert serialized_misc_cost.data == expected

    # Create a booking costing £12
    booking = BookingFactory()
    psg = PerformanceSeatingFactory(performance=booking.performance, price=1200)
    serialized_misc_cost = PercentageMiscCostSerializer(
        percentage_misc_cost, context={"booking": booking}
    )
    expected["value"] = percentage_misc_cost.value(booking)
    assert serialized_misc_cost.data == expected
