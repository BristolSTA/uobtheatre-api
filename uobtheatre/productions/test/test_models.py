# pylint: disable=too-many-lines
import math
import random
from datetime import timedelta
from unittest.mock import PropertyMock, patch

import pytest
from dateutil import parser
from django.utils import timezone
from guardian.shortcuts import assign_perm
from pytest_django.asserts import assertQuerysetEqual

from uobtheatre.bookings.models import Ticket
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
)
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import Card, Cash, SquareOnline
from uobtheatre.productions.exceptions import (
    InvalidConcessionTypeException,
    InvalidSeatGroupException,
    NotEnoughCapacityException,
)
from uobtheatre.productions.models import Performance, PerformanceSeatGroup, Production
from uobtheatre.productions.test.factories import (
    CastMemberFactory,
    ContentWarningFactory,
    CrewMemberFactory,
    CrewRoleFactory,
    PerformanceFactory,
    ProductionFactory,
    ProductionTeamMemberFactory,
)
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.validators import ValidationError
from uobtheatre.venues.test.factories import SeatGroupFactory, VenueFactory

###
# Production
###


@pytest.mark.django_db
def test_production_duration():

    production = ProductionFactory()

    # Create a performance with a long duration
    start = timezone.datetime(
        day=2,
        month=3,
        year=2020,
        hour=12,
        minute=0,
        second=10,
        tzinfo=timezone.get_current_timezone(),
    )
    end = timezone.datetime(
        day=3,
        month=4,
        year=2021,
        hour=13,
        minute=1,
        second=11,
        tzinfo=timezone.get_current_timezone(),
    )
    PerformanceFactory(start=start, end=end, production=production)

    # Create a performance with a short duration
    start = timezone.datetime(
        day=2,
        month=3,
        year=2020,
        hour=12,
        minute=0,
        second=10,
        tzinfo=timezone.get_current_timezone(),
    )
    end = timezone.datetime(
        day=2,
        month=3,
        year=2020,
        hour=13,
        minute=0,
        second=10,
        tzinfo=timezone.get_current_timezone(),
    )
    performance_short = PerformanceFactory(start=start, end=end, production=production)

    assert production.duration == performance_short.duration


@pytest.mark.django_db
def test_production_duration_with_no_performances():

    # Create production with no performances
    production = ProductionFactory()
    assert production.duration is None


@pytest.mark.django_db
def test_get_single_discounts():
    performance = PerformanceFactory()
    # Create a discount
    discount = DiscountFactory(name="Family")
    DiscountRequirementFactory(number=1, discount=discount)
    DiscountRequirementFactory(number=1, discount=discount)

    discount.performances.set([performance])

    assert performance.discounts.count() == 1
    assert len(performance.get_single_discounts()) == 0


@pytest.mark.django_db
def test_concessions():
    performance = PerformanceFactory()
    # Create a discount
    discount_1 = DiscountFactory(name="Student")
    DiscountRequirementFactory(discount=discount_1)
    DiscountRequirementFactory(discount=discount_1)

    discount_2 = DiscountFactory(name="Family")
    DiscountRequirementFactory(discount=discount_2)
    DiscountRequirementFactory(discount=discount_2)

    discount_1.performances.set([performance])
    discount_2.performances.set([performance])

    assert len(performance.concessions()) == 4


@pytest.mark.django_db
def test_price_with_concession():
    performance = PerformanceFactory()
    concession_type = ConcessionTypeFactory()

    # Create a discount
    discount_1 = DiscountFactory(name="Family")
    DiscountRequirementFactory(
        discount=discount_1, number=1, concession_type=concession_type
    )
    DiscountRequirementFactory(discount=discount_1, number=1)

    discount_2 = DiscountFactory(name="Student", percentage=0.1)
    DiscountRequirementFactory(
        discount=discount_2, number=1, concession_type=concession_type
    )

    psg = PerformanceSeatingFactory(performance=performance, price=20)

    discount_1.performances.set([performance])
    discount_2.performances.set([performance])

    assert performance.price_with_concession(concession_type, psg) == 18


@pytest.mark.django_db
def test_str_warning():
    warning = ContentWarningFactory()
    assert str(warning) == warning.short_description


@pytest.mark.django_db
def test_str_crew_role():
    crew_role = CrewRoleFactory()
    assert str(crew_role) == crew_role.name


@pytest.mark.django_db
def test_str_production():
    production = ProductionFactory()
    assert str(production) == production.name


@pytest.mark.django_db
def test_str_cast_member():
    cast_member = CastMemberFactory()
    assert str(cast_member) == cast_member.name


@pytest.mark.django_db
def test_str_crew_member():
    crew_member = CrewMemberFactory()
    assert str(crew_member) == crew_member.name


@pytest.mark.django_db
def test_str_production_team_memeber():
    production_team_memeber = ProductionTeamMemberFactory()
    assert str(production_team_memeber) == production_team_memeber.name


@pytest.mark.django_db
def test_production_slug_is_unique():

    # Create 2 productions with the same name
    prod1 = ProductionFactory(name="show-name")
    prod2 = ProductionFactory(name="show-name")

    # Assert the production slugs are different
    assert prod1.slug != prod2.slug


@pytest.mark.django_db
@pytest.mark.parametrize(
    "performance_disabled, expected",
    [
        ([False, False, False], True),
        ([True, False, False], True),
        ([True, False, True], True),
        ([True, True, True], False),
    ],
)
def test_production_is_bookable(performance_disabled, expected):
    production = ProductionFactory()
    production.performances.set(
        [
            PerformanceFactory(disabled=performance_disabled[perf])
            for perf in performance_disabled
        ]
    )
    for perf in production.performances.all():
        PerformanceSeatingFactory(performance=perf)

    assert production.is_bookable() == expected


@pytest.mark.django_db
def test_production_is_not_bookable_with_no_performances():
    production = ProductionFactory()
    production.performances.set([])

    assert not production.is_bookable()


@pytest.mark.django_db
def test_production_min_price():
    production = ProductionFactory()
    performances = [PerformanceFactory() for i in range(3)]

    for i in range(3):
        PerformanceSeatingFactory(performance=performances[i], price=10 * (i + 1))

    production.performances.set(performances)

    assert production.min_seat_price() == 10


@pytest.mark.django_db
def test_production_min_price_no_perfs():
    production = ProductionFactory()

    assert production.min_seat_price() is None


@pytest.mark.django_db
def test_production_total_capacity():
    perf_1 = PerformanceFactory(capacity=100)
    perf_2 = PerformanceFactory(production=perf_1.production, capacity=150)
    PerformanceSeatingFactory(performance=perf_1, capacity=1000)
    PerformanceSeatingFactory(performance=perf_2, capacity=140)
    perf_1.production.refresh_from_db()

    assert perf_1.production.total_capacity == 240


@pytest.mark.django_db
def test_production_total_tickets_sold():
    perf_1 = PerformanceFactory()
    perf_2 = PerformanceFactory(production=perf_1.production)
    booking_1 = BookingFactory(performance=perf_1)
    booking_2 = BookingFactory(performance=perf_2)

    # 2 tickets in the performance 1
    TicketFactory(booking=booking_1)
    TicketFactory(booking=booking_1)

    # 1 tickets in the performance 1
    TicketFactory(booking=booking_2)

    # A ticket not in the booking
    TicketFactory()

    assert perf_1.production.total_tickets_sold == 3


@pytest.mark.django_db
def test_production_validate():
    production = ProductionFactory()
    error = ValidationError(message="We need that thing.")
    with patch.object(
        Production.VALIDATOR, "validate", return_value=[error]
    ) as validator:
        assert production.validate() == [error]
        validator.assert_called_once()


@pytest.mark.django_db
def test_production_venues():
    production = ProductionFactory()
    venue_1 = VenueFactory()
    venue_2 = VenueFactory()
    VenueFactory()

    PerformanceFactory(production=production, venue=venue_1)
    PerformanceFactory(production=production, venue=venue_1)
    PerformanceFactory(production=production, venue=venue_2)

    assertQuerysetEqual(production.venues.all(), [venue_1, venue_1, venue_2])
    assertQuerysetEqual(production.venues.distinct().all(), [venue_1, venue_2])


###
# Performance
###


@pytest.mark.django_db
@pytest.mark.parametrize(
    "start,end,expected_seconds",
    [
        [
            timezone.datetime(
                day=2,
                month=3,
                year=2020,
                hour=12,
                minute=0,
                second=10,
                tzinfo=timezone.get_current_timezone(),
            ),
            timezone.datetime(
                day=3,
                month=4,
                year=2021,
                hour=13,
                minute=1,
                second=11,
                tzinfo=timezone.get_current_timezone(),
            ),
            34304461.0,
        ],
        [
            None,
            timezone.datetime(
                day=3,
                month=4,
                year=2021,
                hour=13,
                minute=1,
                second=11,
                tzinfo=timezone.get_current_timezone(),
            ),
            None,
        ],
    ],
)
def test_performance_duration(start, end, expected_seconds):
    performance = PerformanceFactory(start=start, end=end)

    if expected_seconds:
        assert performance.duration.total_seconds() == expected_seconds
    else:
        assert performance.duration is None


@pytest.mark.django_db
def test_performance_seat_bookings():

    prod = ProductionFactory()

    perf1 = PerformanceFactory(production=prod)
    perf2 = PerformanceFactory(production=prod)

    # Create a booking for the perf1
    booking1 = BookingFactory(performance=perf1)

    # Create a booking for the perf2
    booking2 = BookingFactory(performance=perf2)

    # Seat group
    seat_group = SeatGroupFactory()

    # Create 3 seat bookings for perf1
    for _ in range(3):
        TicketFactory(booking=booking1)

    # And then 4 more with a given seat bookings for perf1
    for _ in range(4):
        TicketFactory(booking=booking1, seat_group=seat_group)

    # Create 2 seat bookings for perf2
    for _ in range(2):
        TicketFactory(booking=booking2)

    assert perf1.tickets.filter(seat_group=seat_group).count() == 4

    assert perf1.tickets.count() == 7
    assert perf2.tickets.count() == 2


@pytest.mark.django_db
def test_performance_tickets():
    booking = BookingFactory()

    # 2 tickets in the performance
    first_ticket = TicketFactory(booking=booking)
    TicketFactory(booking=booking)

    # A ticket not in the booking
    TicketFactory()

    assert booking.performance.tickets.count() == 2
    assert booking.performance.tickets.all()[0].id == first_ticket.id


@pytest.mark.django_db
def test_performance_checked_in_tickets():
    booking = BookingFactory()

    # 2 tickets in the performance
    TicketFactory(booking=booking)
    ticket = TicketFactory(booking=booking, set_checked_in=True)

    # Ticket in an in progress booking - shouldn't be included
    in_progress_booking = BookingFactory(
        performance=booking.performance, status=Payable.Status.IN_PROGRESS
    )
    TicketFactory(booking=in_progress_booking)

    assert booking.performance.checked_in_tickets.count() == 1
    assert booking.performance.checked_in_tickets.all()[0].id == ticket.id


@pytest.mark.django_db
def test_performance_unchecked_in_tickets():
    booking = BookingFactory()

    # 2 tickets in the performance
    ticket = TicketFactory(booking=booking)
    TicketFactory(booking=booking, set_checked_in=True)

    # Ticket in an in progress booking - shouldn't be included
    in_progress_booking = BookingFactory(
        performance=booking.performance, status=Payable.Status.IN_PROGRESS
    )
    TicketFactory(booking=in_progress_booking)

    assert booking.performance.unchecked_in_tickets.count() == 1
    assert booking.performance.unchecked_in_tickets.all()[0].id == ticket.id


@pytest.mark.django_db
def test_performance_total_tickets_sold():
    # Booking with 2 tickets
    booking = BookingFactory()
    TicketFactory(booking=booking)
    TicketFactory(booking=booking)

    # Draft booking with 3 tickets (shouldn't be counted)
    draft_booking = BookingFactory(status=Payable.Status.IN_PROGRESS)
    TicketFactory(booking=draft_booking)
    TicketFactory(booking=draft_booking)
    TicketFactory(booking=draft_booking)

    # Expired Booking with 4 tickets (shouldn't be counted)
    expires_draft_booking = BookingFactory(
        expires_at=timezone.now() - timedelta(minutes=16),
        status=Payable.Status.IN_PROGRESS,
    )
    TicketFactory(booking=expires_draft_booking)
    TicketFactory(booking=expires_draft_booking)
    TicketFactory(booking=expires_draft_booking)
    TicketFactory(booking=expires_draft_booking)

    # A ticket not in any of the bookings (shouldn't be counted)
    TicketFactory()

    assert booking.performance.total_tickets_sold() == 2


@pytest.mark.django_db
def test_performance_total_tickets_sold_or_reserved():
    # Booking with 2 tickets
    booking = BookingFactory()
    TicketFactory(booking=booking)
    TicketFactory(booking=booking)

    # Draft booking with 3 tickets
    draft_booking = BookingFactory(
        status=Payable.Status.IN_PROGRESS, performance=booking.performance
    )
    TicketFactory(booking=draft_booking)
    TicketFactory(booking=draft_booking)
    TicketFactory(booking=draft_booking)

    # Expired Booking with 4 tickets (shouldn't be counted)
    expires_draft_booking = BookingFactory(
        expires_at=timezone.now() - timedelta(minutes=16),
        status=Payable.Status.IN_PROGRESS,
        performance=booking.performance,
    )
    TicketFactory(booking=expires_draft_booking)
    TicketFactory(booking=expires_draft_booking)
    TicketFactory(booking=expires_draft_booking)
    TicketFactory(booking=expires_draft_booking)

    # A ticket not in any of the bookings (shouldn't be counted)
    TicketFactory()

    assert booking.performance.total_tickets_sold_or_reserved() == 2 + 3


@pytest.mark.django_db
def test_performance_total_tickets_checked_in():
    booking = BookingFactory()

    # 2 tickets in the performance
    TicketFactory(booking=booking)
    TicketFactory(booking=booking, set_checked_in=True)

    assert booking.performance.total_tickets_checked_in == 1
    assert booking.performance.total_tickets_unchecked_in == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "seat_group_capacities,performance_capacity,venue_capacity,expected",
    [
        ([50, 30], None, 100, 80),
        ([50, 200], None, 100, 100),
        ([50, 200], 40, 100, 40),
        ([], 40, 100, 0),
        ([], 40, None, 0),
        ([40], None, None, 40),
    ],
)
def test_performance_total_capacity(
    seat_group_capacities, performance_capacity, venue_capacity, expected
):
    performance = PerformanceFactory(
        venue=VenueFactory(internal_capacity=venue_capacity)
        if not venue_capacity is None
        else None,
        capacity=performance_capacity,
    )

    for capacity in seat_group_capacities:
        PerformanceSeatingFactory(performance=performance, capacity=capacity)

    assert performance.total_capacity == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "total_performance_capacity,seat_groups_capacities_remaining,sold_tickets,expected",
    [
        (
            100,
            [50, 20],
            2,
            70,  # Note that it is seat group capacities __remaining__
        ),
        (
            100,
            [50, 20],
            40,
            60,  # Now the performance becomes the dominating factor
        ),
        (
            100,
            [50, 207],
            2,
            98,
        ),
        (
            100,
            [],
            1,
            0,
        ),
    ],
)
def test_performance_capacity_remaining(
    total_performance_capacity, seat_groups_capacities_remaining, sold_tickets, expected
):
    performance = PerformanceFactory()
    for _ in seat_groups_capacities_remaining:
        PerformanceSeatingFactory(performance=performance)

    with patch(
        "uobtheatre.productions.models.Performance.total_capacity",
        new_callable=PropertyMock(return_value=total_performance_capacity),
    ), patch.object(
        performance,
        "seat_group_capacity_remaining",
        side_effect=seat_groups_capacities_remaining,
    ), patch.object(
        performance, "total_tickets_sold_or_reserved", return_value=sold_tickets
    ):

        assert performance.capacity_remaining == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "total_performance_capacity,total_sold_tickets,total_seat_group_capacity,seat_group_sold_tickets,expected",
    [
        (100, 10, 50, 5, 45),
        (100, 10, 207, 5, 90),
        (100, 10, 207, 127, 80),
    ],
)
def test_performance_seat_group_capacity_remaining(
    total_performance_capacity,
    total_sold_tickets,
    total_seat_group_capacity,
    seat_group_sold_tickets,
    expected,
):
    performance = PerformanceFactory()
    seat_group = PerformanceSeatingFactory().seat_group
    with patch(
        "uobtheatre.productions.models.Performance.total_capacity",
        new_callable=PropertyMock(return_value=total_performance_capacity),
    ), patch.object(
        performance,
        "total_seat_group_capacity",
        return_value=total_seat_group_capacity,
    ) as total_seat_group_capacity_mock, patch.object(
        performance,
        "total_tickets_sold_or_reserved",
        side_effect=lambda seat_group=None: seat_group_sold_tickets
        if seat_group
        else total_sold_tickets,
    ) as total_tickets_sold_or_reserved_mock:

        assert performance.seat_group_capacity_remaining(seat_group) == expected
        total_seat_group_capacity_mock.assert_called_once_with(seat_group=seat_group)
        total_tickets_sold_or_reserved_mock.assert_any_call(seat_group=seat_group)


@pytest.mark.django_db
def test_performance_seat_group_capacity_reamining_with_invalid_seat_group():
    performance = PerformanceFactory()
    assert performance.seat_group_capacity_remaining(SeatGroupFactory()) == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name, start, string",
    [
        ("TRASH", None, "Performance of TRASH"),
        (
            "TRASH",
            "2020-12-27T11:17:43Z",
            "Performance of TRASH at 11:17 on 27/12/2020",
        ),
    ],
)
def test_performance_str(name, start, string):
    production = ProductionFactory(name=name)
    start_date = parser.parse(start) if start else None
    performance = PerformanceFactory(production=production, start=start_date)

    assert str(performance) == string


@pytest.mark.django_db
def test_performance_min_price_free_performance():

    performance = PerformanceFactory()
    PerformanceSeatingFactory(performance=performance, price=0)
    PerformanceSeatingFactory(performance=performance, price=20)

    assert performance.min_seat_price() == 0


@pytest.mark.django_db
def test_performance_min_price_with_single_discounts():
    performance = PerformanceFactory()
    PerformanceSeatingFactory(performance=performance, price=30)
    PerformanceSeatingFactory(performance=performance, price=10)

    adult = ConcessionTypeFactory(name="adult")
    child = ConcessionTypeFactory(name="child")

    null_discount = DiscountFactory(percentage=0, name="adult")
    DiscountRequirementFactory(discount=null_discount, number=1, concession_type=adult)

    single_discount = DiscountFactory(percentage=0.27, name="child")
    DiscountRequirementFactory(
        discount=single_discount, number=1, concession_type=child
    )
    null_discount.performances.set([performance])
    single_discount.performances.set([performance])

    assert performance.min_seat_price() == 8


@pytest.mark.django_db
@pytest.mark.parametrize(
    "seat_groups, performance_capacity, is_valid",
    [
        (
            [
                {
                    "number_of_tickets": 2,
                    "number_of_existing_tickets": 2,
                    "capacity": 4,
                }
            ],
            20,
            True,
        ),
        (
            [
                {
                    "number_of_tickets": 2,
                    "number_of_existing_tickets": 2,
                    "capacity": 4,
                },
                {
                    "number_of_tickets": 5,
                    "number_of_existing_tickets": 11,
                    "capacity": 20,
                },
            ],
            20,
            True,
        ),
        (
            # Check error when not enough performance capacity
            [
                {
                    "number_of_tickets": 2,
                    "number_of_existing_tickets": 2,
                    "capacity": 4,
                },
                {
                    "number_of_tickets": 5,
                    "number_of_existing_tickets": 11,
                    "capacity": 20,
                },
            ],
            15,
            False,
        ),
        (
            # Check error when not enough seat_group capacity
            [
                {
                    "number_of_tickets": 2,
                    "number_of_existing_tickets": 2,
                    "capacity": 4,
                },
                {
                    "number_of_tickets": 5,
                    "number_of_existing_tickets": 11,
                    "capacity": 14,
                },
            ],
            20,
            False,
        ),
        (
            # Check error when both
            [
                {
                    "number_of_tickets": 2,
                    "number_of_existing_tickets": 2,
                    "capacity": 4,
                },
                {
                    "number_of_tickets": 5,
                    "number_of_existing_tickets": 11,
                    "capacity": 14,
                },
            ],
            15,
            False,
        ),
        (
            # Check ok when not deleted tickets mean enough performance capacity
            [
                {
                    "number_of_tickets": 2,
                    "number_of_existing_tickets": 2,
                    "capacity": 4,
                },
                {
                    "number_of_tickets": 5,
                    "number_of_existing_tickets": 11,
                    "number_of_tickets_to_delete": 10,
                    "capacity": 20,
                },
            ],
            15,
            True,
        ),
        (
            # Check ok when enough seat_group capacity because deleted tickets
            [
                {
                    "number_of_tickets": 2,
                    "number_of_existing_tickets": 2,
                    "capacity": 4,
                },
                {
                    "number_of_tickets": 5,
                    "number_of_existing_tickets": 11,
                    "number_of_tickets_to_delete": 2,
                    "capacity": 14,
                },
            ],
            20,
            True,
        ),
    ],
)
def test_performance_validate_tickets(seat_groups, performance_capacity, is_valid):
    performance = PerformanceFactory(capacity=performance_capacity)
    requirement = DiscountRequirementFactory()
    requirement.discount.performances.set([performance])

    tickets_to_book = []
    tickets_to_delete = []

    for seat_group in seat_groups:
        performance_seat_group = PerformanceSeatingFactory(
            performance=performance, capacity=seat_group["capacity"]
        )

        # Create some bookings which create the existing tickets
        number_of_existing_tickets = seat_group["number_of_existing_tickets"]
        bookings = [
            BookingFactory(performance=performance)
            for i in range(math.ceil(number_of_existing_tickets / 2))
        ]
        _ = [
            TicketFactory(
                booking=random.choice(bookings),
                seat_group=performance_seat_group.seat_group,
            )
            for _ in range(number_of_existing_tickets)
        ]

        # Create the ticket which are being checked
        tickets_to_book.extend(
            [
                Ticket(
                    seat_group=performance_seat_group.seat_group,
                    concession_type=requirement.concession_type,
                )
                for i in range(seat_group["number_of_tickets"])
            ]
        )

        tickets_to_delete.extend(
            [
                Ticket(seat_group=performance_seat_group.seat_group)
                for i in range(seat_group.get("number_of_tickets_to_delete", 0))
            ]
        )

    if not is_valid:
        with pytest.raises(NotEnoughCapacityException):
            performance.validate_tickets(
                tickets_to_book, deleted_tickets=tickets_to_delete
            )
    else:
        performance.validate_tickets(tickets_to_book, deleted_tickets=tickets_to_delete)


@pytest.mark.django_db
def test_performance_validate_tickets_seat_group_not_in_performance():
    seat_group = SeatGroupFactory(name="Seat Group 1")

    # Set up some seat groups for a performance
    psg = PerformanceSeatingFactory(
        capacity=100, seat_group=SeatGroupFactory(name="Seat Group 2")
    )
    PerformanceSeatingFactory(
        capacity=100,
        performance=psg.performance,
        seat_group=SeatGroupFactory(name="Seat Group 3"),
    )

    requirement = DiscountRequirementFactory()

    requirement.discount.performances.set([psg.performance])
    booking = BookingFactory(performance=psg.performance)

    # But then try and book a seat group that is not assigned to the performance
    tickets = [
        Ticket(
            seat_group=seat_group,
            booking=booking,
            concession_type=requirement.concession_type,
        )
    ]

    with pytest.raises(InvalidSeatGroupException) as err:
        psg.performance.validate_tickets(tickets=tickets)

    assert (
        err.value.message
        == "You cannot book a seat group that is not assigned to this performance. You have booked Seat Group 1 but the performance only has Seat Group 2, Seat Group 3"
    )


@pytest.mark.django_db
def test_performance_validate_tickets_concession_type_not_in_performance():
    # Create a concession type not assigned to the performance
    concession_type = ConcessionTypeFactory(name="Test concession type")

    # Set up some seat groups for a performance
    psg = PerformanceSeatingFactory(
        capacity=100, seat_group=SeatGroupFactory(name="Seat Group 2")
    )

    booking = BookingFactory(performance=psg.performance)

    # But then try and book a seat group that is not assigned to the performance
    tickets = [
        Ticket(
            seat_group=psg.seat_group, booking=booking, concession_type=concession_type
        )
    ]

    with pytest.raises(InvalidConcessionTypeException) as err:
        psg.performance.validate_tickets(tickets=tickets)

    assert (
        err.value.message
        == f"Test concession type are not assigned to the performance {psg.performance}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "disabled,sold_out,past,expected",
    [
        (False, False, False, True),
        (True, False, False, False),
        (False, True, False, False),
        (False, False, True, False),
    ],
)
def test_performance_is_bookable(disabled, sold_out, past, expected):
    performance = PerformanceFactory(end=timezone.now() + timedelta(days=1))
    PerformanceSeatingFactory(
        performance=performance, capacity=100 if not sold_out else 0
    )

    if past:
        performance.end = timezone.now() - timedelta(days=1)

    performance.disabled = disabled

    assert performance.is_bookable is expected


@pytest.mark.django_db
def test_production_start_and_end_date():
    current_time = timezone.now()

    production = ProductionFactory()

    # Test result with no performances
    assert production.end_date() is None
    assert production.start_date() is None

    _ = [
        PerformanceFactory(
            start=current_time + timezone.timedelta(days=1),
            end=current_time + timezone.timedelta(days=1),
            production=production,
        ),
        PerformanceFactory(
            start=current_time + timezone.timedelta(days=2),
            end=current_time + timezone.timedelta(days=2),
            production=production,
        ),
        PerformanceFactory(
            start=current_time + timezone.timedelta(days=3),
            end=current_time + timezone.timedelta(days=3),
            production=production,
        ),
    ]

    assert production.end_date() == current_time + timezone.timedelta(days=3)
    assert production.start_date() == current_time + timezone.timedelta(days=1)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "performances_start_deltas, is_upcoming",
    [
        ([timezone.timedelta(days=1), timezone.timedelta(days=-1)], True),
        ([timezone.timedelta(hours=1), timezone.timedelta(hours=-1)], True),
        ([timezone.timedelta(days=-1), timezone.timedelta(hours=-1)], False),
        ([timezone.timedelta(hours=-2), timezone.timedelta(hours=-1)], False),
        ([timezone.timedelta(hours=2), timezone.timedelta(hours=1)], True),
    ],
)
def test_is_upcoming_production(performances_start_deltas, is_upcoming):
    now = timezone.now()
    production = ProductionFactory()
    _ = [
        PerformanceFactory(production=production, start=now + start_delta)
        for start_delta in performances_start_deltas
    ]
    assert production.is_upcoming() == is_upcoming


@pytest.mark.django_db
def test_performance_seat_group_default_capacity():
    args = {
        "seat_group": SeatGroupFactory(capacity=100),
        "performance": PerformanceFactory(),
        "price": 10,
    }

    performance = PerformanceSeatGroup(**args)
    performance.save()

    assert performance.capacity == 100


@pytest.mark.django_db
def test_performance_has_boxoffice_permission():
    performance = PerformanceFactory()
    user = UserFactory()

    assert performance.has_boxoffice_permission(user) is False

    assign_perm("boxoffice", user, performance.production)
    assert performance.has_boxoffice_permission(user) is True


@pytest.mark.django_db
def test_qs_has_boxoffice_permission():
    not_has_perm_performances = [PerformanceFactory() for _ in range(3)]
    has_perm_performances = [PerformanceFactory() for _ in range(3)]
    user = UserFactory()

    for perm in has_perm_performances:
        assign_perm("boxoffice", user, perm.production)

    assert (
        list(Performance.objects.has_boxoffice_permission(user))
        == has_perm_performances
    )
    assert (
        list(Performance.objects.has_boxoffice_permission(user, has_permission=False))
        == not_has_perm_performances
    )


@pytest.mark.django_db
def test_qs_running_on():
    query_date = timezone.datetime(
        year=2021, month=7, day=14, tzinfo=timezone.get_current_timezone()
    )
    one_day = timezone.timedelta(days=1)
    # Past performance
    PerformanceFactory(start=query_date - one_day, end=query_date - one_day)
    today_performance = PerformanceFactory(start=query_date, end=query_date)
    spanning_performance_1 = PerformanceFactory(
        start=query_date - one_day, end=query_date
    )
    spanning_performance_2 = PerformanceFactory(
        start=query_date - one_day, end=query_date + one_day
    )
    # Future performance
    PerformanceFactory(start=query_date + one_day, end=query_date + one_day)

    assert list(Performance.objects.running_on(query_date)) == [
        today_performance,
        spanning_performance_1,
        spanning_performance_2,
    ]


@pytest.mark.django_db
def test_has_group_discounts():
    performance = PerformanceFactory()
    assert not performance.has_group_discounts

    # Add a discount with no requirements
    single_discount = DiscountFactory()
    single_discount.performances.set([performance])
    assert not performance.has_group_discounts

    # Create a discount requirement
    DiscountRequirementFactory(discount=single_discount)
    assert not performance.has_group_discounts

    # Create another single discount
    double_discount = DiscountFactory()
    double_discount.performances.set([performance])
    DiscountRequirementFactory(discount=double_discount)
    assert not performance.has_group_discounts

    DiscountRequirementFactory(discount=double_discount)
    assert performance.has_group_discounts


@pytest.mark.django_db
def test_sales_breakdown_production():
    production = ProductionFactory()
    performance_1 = PerformanceFactory(production=production)
    performance_2 = PerformanceFactory(production=production)
    booking_1 = BookingFactory(performance=performance_1)
    booking_2 = BookingFactory(performance=performance_2)

    TransactionFactory(
        pay_object=booking_1,
        provider_fee=2,
        app_fee=100,
        value=200,
        provider_name=Cash.name,
    )
    TransactionFactory(
        pay_object=booking_1,
        provider_fee=4,
        app_fee=200,
        value=600,
        provider_name=Card.name,
    )
    TransactionFactory(
        pay_object=booking_1,
        provider_fee=4,
        app_fee=200,
        value=600,
        provider_name=Card.name,
    )
    TransactionFactory(
        pay_object=booking_1,
        provider_fee=-4,
        app_fee=-200,
        value=-600,
        provider_name=Card.name,
        type=Transaction.Type.REFUND,
    )
    TransactionFactory(
        pay_object=booking_2,
        provider_fee=10,
        app_fee=150,
        value=400,
        provider_name=SquareOnline.name,
    )

    assert production.sales_breakdown() == {
        "app_fee": 450,
        "app_payment_value": 434,
        "provider_payment_value": 16,
        "society_revenue": 750,
        "society_transfer_value": 550,
        "total_card_payments": 1600,
        "total_payments": 1800,
        "total_refunds": -600,
        "total_card_refunds": -600,
        "net_transactions": 1200,
        "net_card_transactions": 1000,
    }


@pytest.mark.django_db
def test_sales_breakdown_performance():
    performance = PerformanceFactory()
    booking_1 = BookingFactory(performance=performance)
    booking_2 = BookingFactory(performance=performance)
    booking_3 = BookingFactory()

    TransactionFactory(
        pay_object=booking_1,
        provider_fee=2,
        app_fee=100,
        value=200,
        provider_name=Cash.name,
    )
    TransactionFactory(
        pay_object=booking_1,
        provider_fee=4,
        app_fee=200,
        value=600,
        provider_name=Card.name,
    )
    TransactionFactory(
        pay_object=booking_2,
        provider_fee=10,
        app_fee=150,
        value=400,
        provider_name=SquareOnline.name,
    )

    TransactionFactory(
        pay_object=booking_3,
        provider_fee=10,
        app_fee=150,
        value=400,
        provider_name=SquareOnline.name,
    )

    assert performance.sales_breakdown() == {
        "app_fee": 450,
        "app_payment_value": 434,
        "provider_payment_value": 16,
        "society_revenue": 750,
        "society_transfer_value": 550,
        "total_card_payments": 1000,
        "total_payments": 1200,
        "total_refunds": 0,
        "total_card_refunds": 0,
        "net_transactions": 1200,
        "net_card_transactions": 1000,
    }


@pytest.mark.django_db
def test_sales_breakdown_with_blank_fees():
    performance = PerformanceFactory()
    booking = BookingFactory(performance=performance)

    TransactionFactory(pay_object=booking, value=200)

    assert performance.sales_breakdown() == {
        "app_fee": 0,
        "app_payment_value": 0,
        "provider_payment_value": 0,
        "society_revenue": 200,
        "society_transfer_value": 200,
        "total_card_payments": 200,
        "total_payments": 200,
        "total_refunds": 0,
        "total_card_refunds": 0,
        "net_transactions": 200,
        "net_card_transactions": 200,
    }


@pytest.mark.django_db
def test_performance_validate():
    performance = PerformanceFactory()
    error = ValidationError(message="We need that thing.")
    with patch.object(
        Performance.VALIDATOR, "validate", return_value=[error]
    ) as validator:
        assert performance.validate() == [error]
        validator.assert_called_once()


@pytest.mark.django_db
def test_performance_validate_without_possible_tickets():
    performance = PerformanceFactory()
    assert performance.validate() is not None

    PerformanceSeatingFactory(performance=performance)

    assert performance.validate() is not None

    performance.discounts.add(DiscountFactory())
    assert performance.validate() is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "disabled,fails",
    [(False, True), (True, False)],
)
def test_performance_refund_bookings(disabled, fails):
    performance = PerformanceFactory(id=1, disabled=disabled)
    user = UserFactory(id=123)

    with patch(
        "uobtheatre.productions.tasks.refund_performance.delay",
    ) as refund_task_mock:

        if fails:
            with pytest.raises(CantBeRefundedException):
                performance.refund_bookings(user)
        else:
            performance.refund_bookings(user)
            refund_task_mock.assert_called_once_with(1, 123)


@pytest.mark.django_db
def test_performance_queryset_bookings():
    performance = PerformanceFactory()
    booking_1 = BookingFactory(performance=performance)
    booking_2 = BookingFactory()  # Booking not in the performance

    assertQuerysetEqual(
        Performance.objects.bookings(), [booking_1, booking_2], ordered=False
    )
    assertQuerysetEqual(
        Performance.objects.filter(pk=performance.pk).bookings(), [booking_1]
    )


@pytest.mark.django_db
def test_performance_queryset_transactions():
    performance = PerformanceFactory()
    transaction_1 = TransactionFactory(
        pay_object=BookingFactory(performance=performance)
    )
    transaction_2 = TransactionFactory()  # Transaction not in the performance

    assertQuerysetEqual(
        Performance.objects.transactions().all(),
        [transaction_1, transaction_2],
        ordered=False,
    )
    assertQuerysetEqual(
        Performance.objects.filter(pk=performance.pk).transactions().all(),
        [transaction_1],
    )


@pytest.mark.django_db
def test_production_queryset_performances():
    performance_1 = PerformanceFactory()
    performance_2 = PerformanceFactory()

    assertQuerysetEqual(
        Production.objects.performances().all(),
        [performance_1, performance_2],
        ordered=False,
    )
    assertQuerysetEqual(
        Production.objects.filter(pk=performance_1.production.pk).performances().all(),
        [performance_1],
    )


@pytest.mark.django_db
def test_production_queryset_transactions():
    transaction_1 = TransactionFactory()
    transaction_2 = TransactionFactory()

    assertQuerysetEqual(
        Production.objects.transactions().all(),
        [transaction_1, transaction_2],
        ordered=False,
    )
    assertQuerysetEqual(
        Production.objects.filter(pk=transaction_1.pay_object.performance.production.pk)
        .transactions()
        .all(),
        [transaction_1],
    )


@pytest.mark.django_db
def test_performances_booked_users():
    performance_1 = PerformanceFactory()
    # Refunded payable - Refunded
    booking_1 = BookingFactory(performance=performance_1)
    TransactionFactory(value=2, pay_object=booking_1)

    booking_2 = BookingFactory(performance=performance_1)
    TransactionFactory(value=-2, pay_object=booking_2)

    # Not included as booking refunded
    booking_3 = BookingFactory(performance=performance_1)
    TransactionFactory(value=2, pay_object=booking_3)
    TransactionFactory(value=-2, pay_object=booking_3)

    # Not included as in progress
    booking_4 = BookingFactory(
        performance=performance_1, status=Payable.Status.IN_PROGRESS
    )

    print(booking_4.status)
    # Make another booking for the same user and assert it only shows up once
    performance_2 = PerformanceFactory()
    TransactionFactory(
        value=2,
        pay_object=BookingFactory(performance=performance_2, user=booking_1.user),
    )

    assertQuerysetEqual(
        Performance.objects.filter(
            pk__in=[performance_1.pk, performance_2.pk]
        ).booked_users(),
        [booking_1.user, booking_2.user],
        ordered=False,
    )
