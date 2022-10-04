# pylint: disable=too-many-lines

import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.test.factories import mock_transferable
from uobtheatre.payments.transferables import Transferable


@pytest.mark.django_db
def test_transferred_to():
    booking_3 = BookingFactory()
    booking_2 = BookingFactory(transferred_from=booking_3)
    booking_1 = BookingFactory(transferred_from=booking_2)

    booking_4 = BookingFactory()

    assert booking_1.transferred_to is None
    assert booking_4.transferred_to is None
    assert booking_2.transferred_to == booking_1
    assert booking_3.transferred_to == booking_2


@pytest.mark.parametrize(
    "booking, expected_total",
    [
        pytest.param(
            {"subtotal": 0, "misc_costs_value": 100},
            0,
            id="free transfers have no misc costs",
        ),
        pytest.param(
            {"subtotal": 800, "misc_costs_value": 100}, 900, id="without transfer"
        ),
        pytest.param(
            {
                "subtotal": 800,
                "misc_costs_value": 100,
                "transferred_from": {"subtotal": 200, "misc_costs_value": 50},
            },
            850,  # New Booking Value: 900. Old Booking Value: 250. To Pay = 900 - 250 + 200 (Transfer Fee) = 850
            id="calculates correct value",
        ),
        pytest.param(
            {
                "subtotal": 800,
                "misc_costs_value": 100,
                "transferred_from": {"subtotal": 1000, "misc_costs_value": 50},
            },
            200,  # New Booking Value: 900. Old Booking Value: 1050. To Pay = max(0, -150) + 200 (Transfer Fee) = 200
            id="calculates correct value when original booking is larger than new booking",
        ),
        pytest.param(
            {
                "subtotal": 50,
                "misc_costs_value": 10,
                "transferred_from": {"subtotal": 20, "misc_costs_value": 10},
            },
            230,  # New Booking Value: 60. Old Booking Value: 30. To Pay = 30 + 200 (Transfer Fee) = 230
            id="calculates correct value with small totals",
        ),
        pytest.param(
            {
                "subtotal": 0,
                "misc_costs_value": 10,
                "transferred_from": {"subtotal": 20, "misc_costs_value": 10},
            },
            0,
            id="should be free if subtotal is 0",
        ),
        pytest.param(
            {
                "subtotal": 1000,
                "misc_costs_value": 100,
                "transferred_from": {
                    "subtotal": 2000,
                    "misc_costs_value": 200,
                    "transferred_from": {"subtotal": 1000, "misc_costs_value": 100},
                },
            },
            200,  # New Booking Value: 1100. Old Booking Value: 2200. To Pay = max(0, -1100) + 200 (Transfer Fee) = 200
            id="calculates correct value with nested transfers when inital transferred_from is larger than the new booking",
        ),
        pytest.param(
            {
                "subtotal": 2000,
                "misc_costs_value": 200,
                "transferred_from": {
                    "subtotal": 1000,
                    "misc_costs_value": 100,
                    "transferred_from": {"subtotal": 1000, "misc_costs_value": 100},
                },
            },
            1300,  # New Booking Value: 2200. Old Booking Value: 1100. To Pay = 2200 - 1100 + 200 (Transfer Fee) = 1300
            id="calculates correct value with nested transfers when inital transferred_from is smaller than the new booking",
        ),
    ],
)
def test_transferable_total(booking, expected_total):
    def create_transferable(transferable: dict) -> Transferable:
        transferred_from = transferable.pop("transferred_from", None)
        return mock_transferable(
            **transferable,
            transferred_from=create_transferable(transferred_from)
            if transferred_from
            else None
        )

    # pylint: disable=missing-class-docstring
    transferable = create_transferable(booking)
    assert transferable.total == expected_total
