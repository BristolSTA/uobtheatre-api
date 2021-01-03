import pytest

from uobtheatre.bookings.models import Booking, PercentageMiscCost, ValueMiscCost
from uobtheatre.bookings.serializers import (
    BookingSerialiser,
    CreateBookingSerialiser,
    CreateTicketSerializer,
    DiscountSerializer,
    PercentageMiscCostSerializer,
    ValueMiscCostSerializer,
)
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
    PercentageMiscCostFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_booking_serializer_wo_tickets_misc(date_format):
    booking = BookingFactory()
    data = Booking.objects.first()
    serialized_booking = BookingSerialiser(data)

    performance = {
        "id": booking.performance.id,
        "production_id": booking.performance.production.id,
        "venue": {
            "id": booking.performance.venue.id,
            "name": booking.performance.venue.name,
            "publicly_listed": booking.performance.venue.publicly_listed,
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
        "price_breakdown": {
            "tickets": [],
            "tickets_price": booking.tickets_price(),
            "discounts_value": booking.discount_value(),
            "subtotal_price": booking.subtotal(),
            "misc_costs": [],
            "misc_costs_value": booking.misc_costs_value(),
            "total_price": booking.total(),
        },
        "status": booking.status,
    }


@pytest.mark.django_db
def test_booking_serializer_price_break_down(date_format):
    booking = BookingFactory()
    data = Booking.objects.first()
    serialized_booking = BookingSerialiser(data)

    # Create 3 tickets with the same seat group and concession type
    seat_group_1 = SeatGroupFactory()
    psg_1 = PerformanceSeatingFactory(
        performance=booking.performance, seat_group=seat_group_1
    )
    concession_type_1 = ConcessionTypeFactory()
    _ = [
        TicketFactory(
            seat_group=seat_group_1, concession_type=concession_type_1, booking=booking
        )
        for _ in range(3)
    ]

    # Create 2 with the same seat group but a different concession type
    concession_type_2 = ConcessionTypeFactory()
    _ = [
        TicketFactory(
            seat_group=seat_group_1, concession_type=concession_type_2, booking=booking
        )
        for _ in range(2)
    ]

    # Create 2 with the same concession but a different seat groups
    seat_group_2 = SeatGroupFactory()
    psg_2 = PerformanceSeatingFactory(
        performance=booking.performance, seat_group=seat_group_2
    )
    _ = [
        TicketFactory(
            seat_group=seat_group_2, concession_type=concession_type_1, booking=booking
        )
        for _ in range(2)
    ]

    expected_ticket_groups = [
        {
            "seat_group": seat_group_1,
            "concession_type": concession_type_1,
            "number": 3,
            "price": psg_1.price,
        },
        {
            "seat_group": seat_group_1,
            "concession_type": concession_type_2,
            "number": 2,
            "price": psg_1.price,
        },
        {
            "seat_group": seat_group_2,
            "concession_type": concession_type_1,
            "number": 2,
            "price": psg_2.price,
        },
    ]

    # Add in some misc costs
    value_misc_costs = [ValueMiscCostFactory() for _ in range(2)]
    percentage_misc_cost = [ValueMiscCostFactory() for _ in range(2)]

    def misc_cost_to_dict(misc_cost):
        misc_cost_expected = {
            "name": misc_cost.name,
            "description": misc_cost.description,
            "value": misc_cost.value
            if isinstance(misc_cost, ValueMiscCost)
            else misc_cost.value,
        }
        if isinstance(misc_cost, PercentageMiscCost):
            misc_cost_expected["percentage"] = misc_cost.percentage
        return misc_cost_expected

    misc_cost_expected = list(
        map(misc_cost_to_dict, value_misc_costs + percentage_misc_cost)
    )

    # Check 3 types of tickets
    assert len(serialized_booking.data["price_breakdown"]["tickets"]) == 3
    assert serialized_booking.data["price_breakdown"] == {
        "tickets": [
            {
                "ticket_price": ticket_group["price"],
                "number": ticket_group["number"],
                "seat_group": {
                    "id": ticket_group["seat_group"].id,
                    "name": ticket_group["seat_group"].name,
                    "description": ticket_group["seat_group"].description,
                    "capacity": ticket_group["seat_group"].capacity,
                    "is_internal": ticket_group["seat_group"].is_internal,
                    "venue": ticket_group["seat_group"].venue.id,
                    "seats": ticket_group["seat_group"].seats,
                },
                "concession_type": {
                    "id": ticket_group["concession_type"].id,
                    "name": ticket_group["concession_type"].name,
                    "description": ticket_group["concession_type"].description,
                },
                "total_price": ticket_group["number"] * ticket_group["price"],
            }
            for ticket_group in expected_ticket_groups
        ],
        "tickets_price": booking.tickets_price(),
        "discounts_value": booking.discount_value(),
        "subtotal_price": booking.subtotal(),
        "misc_costs": misc_cost_expected,
        "misc_costs_value": booking.misc_costs_value(),
        "total_price": booking.total(),
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
    SeatBooking()
    data = SeatBooking.objects.first()
    CreateSeatBookingSerialiser(data)


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
