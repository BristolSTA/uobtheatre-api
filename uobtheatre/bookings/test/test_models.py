import pytest

from uobtheatre.bookings.models import Discount, DiscountRequirement, combinations
from uobtheatre.bookings.test.factories import (
    DiscountFactory,
    ConsessionTypeFactory,
    BookingFactory,
)
from uobtheatre.productions.test.factories import PerformanceFactory
from collections import Counter


@pytest.mark.parametrize(
    "input, length, output",
    [
        (
            [1, 2, 3],
            2,
            [
                (1,),
                (2,),
                (3,),
                (1, 1),
                (1, 2),
                (1, 3),
                (2, 1),
                (2, 2),
                (2, 3),
                (3, 1),
                (3, 2),
                (3, 3),
            ],
        ),
        (
            [1, 2, 3],
            3,
            [
                (1,),
                (2,),
                (3,),
                (1, 1),
                (1, 2),
                (1, 3),
                (2, 1),
                (2, 2),
                (2, 3),
                (3, 1),
                (3, 2),
                (3, 3),
                (1, 1, 1),
                (1, 1, 2),
                (1, 1, 3),
                (1, 2, 1),
                (1, 2, 2),
                (1, 2, 3),
                (1, 3, 1),
                (1, 3, 2),
                (1, 3, 3),
                (2, 1, 1),
                (2, 1, 2),
                (2, 1, 3),
                (2, 2, 1),
                (2, 2, 2),
                (2, 2, 3),
                (2, 3, 1),
                (2, 3, 2),
                (2, 3, 3),
                (3, 1, 1),
                (3, 1, 2),
                (3, 1, 3),
                (3, 2, 1),
                (3, 2, 2),
                (3, 2, 3),
                (3, 3, 1),
                (3, 3, 2),
                (3, 3, 3),
            ],
        ),
    ],
)
def test_combinations(input, length, output):
    calculated_combinations = combinations(input, length)
    assert set(calculated_combinations) == set(output)
    assert len(calculated_combinations) == len(output)


@pytest.mark.django_db
def test_is_valid_discount():
    booking = BookingFactory()
    discount = DiscountFactory()
    discount.performance = booking.performance

    # Add some requirements to the discount
    consession_type_student = ConsessionTypeFactory(name="Student")
    discount_requirements = DiscountRequirement(
        consession_type=consession_type_student, number=1, discount=discount
    )

    # assert not booking.is_valid_discount_combination((discount,))


def test_get_valid_discounts():
    pass
