import pytest
from django.core.exceptions import ValidationError

from uobtheatre.discounts.models import Discount, DiscountRequirement
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
)
from uobtheatre.productions.test.factories import PerformanceFactory


@pytest.mark.django_db
def test_cannot_create_2_discounts_with_the_same_requirements():
    dis_1 = DiscountFactory()
    dis_2 = DiscountFactory()
    perf = PerformanceFactory()
    dis_1.performances.set([perf])
    dis_2.performances.set([perf])

    requirement_1 = DiscountRequirementFactory(discount=dis_1)

    # Assert when discount 1 has these requirements it is unique
    dis_1.validate_unique()

    DiscountRequirementFactory(
        discount=dis_2,
        concession_type=requirement_1.concession_type,
        number=requirement_1.number,
    )

    with pytest.raises(ValidationError):
        dis_1.validate_unique()

    # Change the performance, to make unique
    dis_1.performances.set([PerformanceFactory()])

    dis_1.validate_unique()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "num_requirements,same_performance",
    [(0, False), (1, False), (2, False), (0, True), (1, True), (2, True)],
)
def test_discount_with_requirements_and_performances(
    num_requirements, same_performance
):
    concessions = [ConcessionTypeFactory() for _ in range(num_requirements)]
    performance_1 = PerformanceFactory()
    performance_2 = PerformanceFactory()

    dis_1 = DiscountFactory()
    dis_2 = DiscountFactory()
    dis_1.performances.set([performance_1])
    dis_2.performances.set([performance_1 if same_performance else performance_2])

    dis_1.requirements.set(
        [
            DiscountRequirementFactory(concession_type=concession)
            for concession in concessions
        ]
    )
    dis_2.requirements.set(
        [
            DiscountRequirement(concession_type=concession, number=1)
            for concession in concessions
        ],
        bulk=False,
    )

    if same_performance:
        with pytest.raises(ValidationError):
            dis_2.validate_unique()
    else:
        dis_2.validate_unique()


@pytest.mark.django_db
def test_discount_without_exclusion_unique_requirement():
    DiscountFactory()
    dis_2 = Discount()

    dis_2.validate_unique()
