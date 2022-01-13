import pytest

from uobtheatre.discounts.models import Discount
from uobtheatre.discounts.schema import DiscountFilter
from uobtheatre.discounts.test.factories import (
    DiscountFactory,
    DiscountRequirementFactory,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filter_value",
    [
        (True),
        (False),
    ],
)
def test_discount_filter_group(filter_value):
    group_discount = DiscountFactory()
    DiscountRequirementFactory(discount=group_discount, number=2)

    single_discount = DiscountFactory()
    DiscountRequirementFactory(discount=single_discount, number=1)

    result_qs = DiscountFilter().filter_group(Discount.objects, None, filter_value)

    if filter_value:
        assert group_discount in list(result_qs.all())

    if not filter_value:
        assert single_discount in list(result_qs.all())
