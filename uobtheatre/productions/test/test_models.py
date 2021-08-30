import math
import random

import pytest
from dateutil import parser
from django.utils import timezone
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.models import Booking, Ticket
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
from uobtheatre.payments.test.factories import PaymentFactory
from uobtheatre.productions.models import Performance, PerformanceSeatGroup
from uobtheatre.productions.test.factories import (
    AudienceWarningFactory,
    CastMemberFactory,
    CrewMemberFactory,
    CrewRoleFactory,
    PerformanceFactory,
    ProductionFactory,
    ProductionTeamMemberFactory,
)
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_performance_duration():
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
    performance = PerformanceFactory(start=start, end=end)

    assert performance.duration().total_seconds() == 34304461.0


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

    assert production.duration() == performance_short.duration()


@pytest.mark.django_db
def test_production_duration_with_no_performances():

    # Create production with no performances
    production = ProductionFactory()
    assert production.duration() is None


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
    warning = AudienceWarningFactory()
    assert str(warning) == warning.description


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
    ticket = TicketFactory(booking=booking, checked_in=True)

    assert booking.performance.checked_in_tickets.count() == 1
    assert booking.performance.checked_in_tickets.all()[0].id == ticket.id


@pytest.mark.django_db
def test_performance_unchecked_in_tickets():
    booking = BookingFactory()

    # 2 tickets in the performance
    ticket = TicketFactory(booking=booking)
    TicketFactory(booking=booking, checked_in=True)

    assert booking.performance.unchecked_in_tickets.count() == 1
    assert booking.performance.unchecked_in_tickets.all()[0].id == ticket.id


@pytest.mark.django_db
def test_performance_total_tickets_sold():
    booking = BookingFactory()

    # 2 tickets in the performance
    TicketFactory(booking=booking)
    TicketFactory(booking=booking)

    # A ticket not in the booking
    TicketFactory()

    assert booking.performance.total_tickets_sold() == 2


@pytest.mark.django_db
def test_performance_total_tickets_checked_in():
    booking = BookingFactory()

    # 2 tickets in the performance
    TicketFactory(booking=booking)
    TicketFactory(booking=booking, checked_in=True)

    assert booking.performance.total_tickets_checked_in == 1
    assert booking.performance.total_tickets_unchecked_in == 1


@pytest.mark.django_db
def test_performance_total_capacity():
    perf = PerformanceFactory()

    seating = [PerformanceSeatingFactory(performance=perf) for _ in range(3)]

    assert (
        perf.total_capacity() == sum(perf_seat.capacity for perf_seat in seating) != 0
    )

    seat_group = SeatGroupFactory()
    assert perf.total_capacity(seat_group) == 0

    seating[0].seat_group = seat_group
    seating[0].save()
    assert perf.total_capacity(seat_group) == seating[0].capacity != 0


@pytest.mark.django_db
def test_performance_capacity_remaining():
    perf = PerformanceFactory()

    seating = [PerformanceSeatingFactory(performance=perf) for _ in range(3)]

    # Check total capacity is the same as capacity_remaining when no bookings
    assert perf.capacity_remaining() == perf.total_capacity()

    seat_group = SeatGroupFactory()
    assert perf.total_capacity(seat_group) == 0

    seating[0].seat_group = seat_group
    seating[0].save()
    assert perf.capacity_remaining(seat_group) == perf.total_capacity(seat_group) != 0

    # Create some tickets for this performance
    booking_1 = BookingFactory(performance=perf)
    booking_2 = BookingFactory(performance=perf)
    _ = [TicketFactory(booking=booking_1, seat_group=seat_group) for _ in range(3)]
    _ = [TicketFactory(booking=booking_2, seat_group=seat_group) for _ in range(2)]
    assert perf.capacity_remaining(seat_group) == perf.total_capacity(seat_group) - 5
    assert perf.capacity_remaining() == perf.total_capacity() - 5


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name, start, string",
    [
        ("TRASH", None, "Perforamce of TRASH"),
        ("TRASH", "2020-12-27T11:17:43Z", "Perforamce of TRASH at 11:17 on 27/12/2020"),
    ],
)
def test_performance_str(name, start, string):
    production = ProductionFactory(name=name)
    start_date = parser.parse(start) if start else None
    performance = PerformanceFactory(production=production, start=start_date)

    assert str(performance) == string


@pytest.mark.django_db
def test_performance_min_price():

    performance = PerformanceFactory()
    PerformanceSeatingFactory(performance=performance, price=30)
    PerformanceSeatingFactory(performance=performance, price=10)
    PerformanceSeatingFactory(performance=performance, price=20)

    assert performance.min_seat_price() == 10


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
def test_performance_check_capacity(seat_groups, performance_capacity, is_valid):
    performance = PerformanceFactory(capacity=performance_capacity)
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
                Ticket(seat_group=performance_seat_group.seat_group)
                for i in range(seat_group["number_of_tickets"])
            ]
        )

        tickets_to_delete.extend(
            [
                Ticket(seat_group=performance_seat_group.seat_group)
                for i in range(seat_group.get("number_of_tickets_to_delete", 0))
            ]
        )

    # If valid this should be none if not it should return something
    assert (
        performance.check_capacity(tickets_to_book, deleted_tickets=tickets_to_delete)
        is None
    ) == is_valid


@pytest.mark.django_db
def test_performance_check_capacity_seat_group_not_in_perforamnce():
    seat_group = SeatGroupFactory()

    # Set up some seat groups for a performance
    psg = PerformanceSeatingFactory(capacity=100)
    psg2 = PerformanceSeatingFactory(capacity=100, performance=psg.performance)
    booking = BookingFactory(performance=psg.performance)

    # But then try and book a seat group that is not assigned to the performance
    tickets = [Ticket(seat_group=seat_group, booking=booking)]

    assert (
        psg.performance.check_capacity(tickets=tickets)
        == f"You cannot book a seat group that is not assigned to this performance, you have booked {seat_group} but the performance only has {psg.seat_group}, {psg2.seat_group}"
    )


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
    query_date = timezone.datetime(year=2021, month=7, day=14)
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
def test_sales_breakdown_on_production():
    production = ProductionFactory()

    def asser_breakdown_values(
        production, payments_value, misc_costs_value, society_income
    ):
        assert production.sales_breakdown["payments_total"] == payments_value
        assert production.sales_breakdown["misc_costs_total"] == misc_costs_value
        assert production.sales_breakdown["society_income_total"] == society_income

    # Blank production should have no sales
    asser_breakdown_values(production, 0, 0, 0)

    # Add a performance with 1 draft, 1 paid and one comp booking
    performance = PerformanceFactory(production=production)
    perf_seat_group = PerformanceSeatingFactory(performance=performance, price=100)

    # Make a misc cost
    ValueMiscCostFactory(value=100)

    booking_1 = BookingFactory(
        status=Booking.BookingStatus.IN_PROGRESS, performance=performance
    )

    # Both bookings have a tickets value of 200, and a misc cost of 0
    booking_2 = BookingFactory(
        status=Booking.BookingStatus.PAID, performance=performance
    )
    booking_3 = BookingFactory(
        status=Booking.BookingStatus.PAID,
        admin_discount_percentage=1,
        performance=performance,
    )

    TicketFactory(booking=booking_1, seat_group=perf_seat_group.seat_group)
    TicketFactory(booking=booking_2, seat_group=perf_seat_group.seat_group)
    TicketFactory(booking=booking_2, seat_group=perf_seat_group.seat_group)
    TicketFactory(booking=booking_3, seat_group=perf_seat_group.seat_group)
    TicketFactory(booking=booking_3, seat_group=perf_seat_group.seat_group)
    PaymentFactory(pay_object=booking_2, value=booking_2.total())

    asser_breakdown_values(production, 300, 100, 200)


@pytest.mark.django_db
def test_sales_breakdown_on_performance():
    performance = PerformanceFactory()

    def asser_breakdown_values(
        performance, payments_total, misc_costs_total, society_income
    ):
        assert performance.sales_breakdown["payments_total"] == payments_total
        assert performance.sales_breakdown["misc_costs_total"] == misc_costs_total
        assert performance.sales_breakdown["society_income_total"] == society_income

    # Blank performance should have no sales
    asser_breakdown_values(performance, 0, 0, 0)

    # Add a performance with 1 draft, 1 paid and one comp booking
    perf_seat_group = PerformanceSeatingFactory(performance=performance, price=150)

    # Make a misc cost
    ValueMiscCostFactory(value=100)

    booking_1 = BookingFactory(
        status=Booking.BookingStatus.IN_PROGRESS, performance=performance
    )

    # Both bookings have a tickets value of 200, and a misc cost of 0
    booking_2 = BookingFactory(
        status=Booking.BookingStatus.PAID, performance=performance
    )
    booking_3 = BookingFactory(
        status=Booking.BookingStatus.PAID,
        admin_discount_percentage=1,
        performance=performance,
    )

    TicketFactory(booking=booking_1, seat_group=perf_seat_group.seat_group)
    TicketFactory(booking=booking_2, seat_group=perf_seat_group.seat_group)
    TicketFactory(booking=booking_2, seat_group=perf_seat_group.seat_group)
    TicketFactory(booking=booking_3, seat_group=perf_seat_group.seat_group)
    TicketFactory(booking=booking_3, seat_group=perf_seat_group.seat_group)
    PaymentFactory(pay_object=booking_2, value=booking_2.total())

    asser_breakdown_values(performance, 400, 100, 300)
