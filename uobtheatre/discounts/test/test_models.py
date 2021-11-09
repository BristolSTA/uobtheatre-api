import pytest
from django.core.exceptions import ValidationError

from uobtheatre.discounts.models import DiscountRequirement
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
)


@pytest.mark.django_db
def test_cannot_create_2_discounts_with_the_same_requirements():
    dis_1 = DiscountFactory()
    dis_2 = DiscountFactory()

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

    # Change the percentage, to make unique
    dis_1.percentage = 0.3

    dis_1.validate_unique()


@pytest.mark.django_db
@pytest.mark.parametrize("num_requirements", [0, 1, 2])
def test_discount_with_same_requirements_is_not_unique(num_requirements):
    concessions = [ConcessionTypeFactory() for _ in range(num_requirements)]

    dis_1 = DiscountFactory(percentage=0.2)
    dis_2 = DiscountFactory(percentage=0.2)

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

    with pytest.raises(ValidationError):
        dis_2.validate_unique()
