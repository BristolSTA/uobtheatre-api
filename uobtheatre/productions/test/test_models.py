import datetime
import pytest
from django.utils import timezone

from uobtheatre.productions.test.factories import (
    PerformanceFactory,
    ProductionFactory,
    CrewMemberFactory,
    CastMemberFactory,
    WarningFactory,
)
from uobtheatre.bookings.test.factories import (
    DiscountFactory,
    DiscountRequirementFactory,
    ConsessionTypeFactory,
    BookingFactory,
    TicketFactory,
    PerformanceSeatingFactory,
    TicketFactory,
)
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_performance_duration():
    start = datetime.datetime(day=2, month=3, year=2020, hour=12, minute=0, second=10)
    end = datetime.datetime(day=3, month=4, year=2021, hour=13, minute=1, second=11)
    performance = PerformanceFactory(start=start, end=end)

    assert performance.duration().total_seconds() == 34304461.0


@pytest.mark.django_db
def test_production_duration():

    production = ProductionFactory()

    # Create a performance with a long duration
    start = datetime.datetime(
        day=2,
        month=3,
        year=2020,
        hour=12,
        minute=0,
        second=10,
        tzinfo=timezone.get_current_timezone(),
    )
    end = datetime.datetime(
        day=3,
        month=4,
        year=2021,
        hour=13,
        minute=1,
        second=11,
        tzinfo=timezone.get_current_timezone(),
    )
    performance_long = PerformanceFactory(start=start, end=end, production=production)

    # Create a performance with a short duration
    start = datetime.datetime(
        day=2,
        month=3,
        year=2020,
        hour=12,
        minute=0,
        second=10,
        tzinfo=timezone.get_current_timezone(),
    )
    end = datetime.datetime(
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
    assert production.duration() == None


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
def test_consessions():
    performance = PerformanceFactory()
    # Create a discount
    discount_1 = DiscountFactory(name="Student")
    discounts_requirement_1 = DiscountRequirementFactory(discount=discount_1)
    discounts_requirement_2 = DiscountRequirementFactory(discount=discount_1)

    discount_2 = DiscountFactory(name="Family")
    discounts_requirement_3 = DiscountRequirementFactory(discount=discount_2)
    discounts_requirement_4 = DiscountRequirementFactory(discount=discount_2)

    discount_1.performances.set([performance])
    discount_2.performances.set([performance])

    assert len(performance.consessions()) == 4


@pytest.mark.django_db
def test_get_consession_discount():
    performance = PerformanceFactory()
    consession_type = ConsessionTypeFactory()
    # Create a discount
    discount_1 = DiscountFactory(name="Family")
    DiscountRequirementFactory(
        discount=discount_1, number=1, consession_type=consession_type
    )
    DiscountRequirementFactory(discount=discount_1, number=1)

    discount_2 = DiscountFactory(name="Student")
    discount_requirement_3 = DiscountRequirementFactory(
        discount=discount_2, number=1, consession_type=consession_type
    )

    discount_1.performances.set([performance])
    discount_2.performances.set([performance])

    assert (
        performance.get_conession_discount(consession_type)
        == discount_requirement_3.discount.discount
    )


@pytest.mark.django_db
def test_get_consession_discount():
    performance = PerformanceFactory()
    consession_type = ConsessionTypeFactory()
    # Create a discount
    discount_1 = DiscountFactory(name="Family")
    DiscountRequirementFactory(
        discount=discount_1, number=1, consession_type=consession_type
    )
    DiscountRequirementFactory(discount=discount_1, number=1)

    discount_2 = DiscountFactory(name="Student", discount=0.1)
    discount_requirement_3 = DiscountRequirementFactory(
        discount=discount_2, number=1, consession_type=consession_type
    )

    discount_1.performances.set([performance])
    discount_2.performances.set([performance])

    assert performance.price_with_consession(consession_type, 20) == 18


@pytest.mark.django_db
def test_str_warning():
    warning = WarningFactory()
    assert str(warning) == warning.warning


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
def test_production_slug_is_unique():

    # Create 2 productions with the same name
    prod1 = ProductionFactory(name="show-name")
    prod2 = ProductionFactory(name="show-name")

    # Assert the production slugs are different
    assert prod1.slug != prod2.slug


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

    assert len(perf1.tickets(seat_group)) == 4

    assert len(perf1.tickets()) == 7
    assert len(perf2.tickets()) == 2


@pytest.mark.django_db
def test_performance_total_capacity():
    perf = PerformanceFactory()

    seating = [PerformanceSeatingFactory(performance=perf) for _ in range(3)]

    assert (
        perf.total_capacity() == sum(perf_seat.capacity for perf_seat in seating) != 0
    )

    seat_group = SeatGroupFactory()
    assert perf.total_capacity(seat_group) == 0

    assert len(perf.performance_seat_groups.all()) == 3
    seating[0].seat_group = seat_group
    assert seating[0].seat_group == seat_group
    assert seating[0].performance == perf
    assert len(perf.performance_seat_groups.get(seat_group=seat_group)) == 1
    assert perf.total_capacity(seat_group) == seating[0].capacity != 0
