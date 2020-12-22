import datetime
import pytest

from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.bookings.test.factories import (
    DiscountFactory,
    DiscountRequirementFactory,
    ConsessionTypeFactory,
)


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
    start = datetime.datetime(day=2, month=3, year=2020, hour=12, minute=0, second=10)
    end = datetime.datetime(day=3, month=4, year=2021, hour=13, minute=1, second=11)
    performance_long = PerformanceFactory(start=start, end=end, production=production)

    # Create a performance with a short duration
    start = datetime.datetime(day=2, month=3, year=2020, hour=12, minute=0, second=10)
    end = datetime.datetime(day=2, month=3, year=2020, hour=13, minute=0, second=10)
    performance_short = PerformanceFactory(start=start, end=end, production=production)

    assert production.duration() == performance_short.duration()


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
        == discount_requirement_3.discount
    )
