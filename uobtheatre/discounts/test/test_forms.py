
import pytest

from uobtheatre.discounts.forms import DiscountForm
from uobtheatre.discounts.test.factories import DiscountFactory
from uobtheatre.productions.test.factories import PerformanceFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "num_exisiting_performances,num_supplied_performances,should_fail",
    [
        (0, 0, True),
        (2, 0, True),
        (2, None, False),
        (2, 2, False),
        (None, 2, False),
        (None, 0, True),
    ],
)
def test_discount_form_clean_with_exisiting(
    num_exisiting_performances, num_supplied_performances, should_fail
):
    exisiting_instance = DiscountFactory()

    # Add exisiting performances
    for _ in range(num_exisiting_performances or 0):
        exisiting_instance.performances.add(PerformanceFactory())

    form_data = {"percentage": 0.1}

    # Add supplied performances
    if not num_supplied_performances is None:
        form_data["performances"] = [
            PerformanceFactory().id for _ in range(num_supplied_performances)
        ]

    form = DiscountForm(
        instance=(
            exisiting_instance if num_exisiting_performances is not None else None
        ),
        data=form_data,
    )

    assert form.errors == (
        {}
        if not should_fail
        else {"performances": ["Please select at least one performance"]}
    )
