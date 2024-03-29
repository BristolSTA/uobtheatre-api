# pylint: disable=too-many-lines
import datetime
import math
from unittest.mock import PropertyMock, patch
from urllib.parse import quote_plus

import pytest
import pytz
from django.db.utils import IntegrityError
from django.utils import timezone
from graphql_relay.node.node import to_global_id

from uobtheatre.bookings.models import Booking, MiscCost, Ticket
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PercentageMiscCostFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.discounts.models import DiscountCombination
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
)
from uobtheatre.payments.exceptions import (
    CantBePaidForException,
    CantBeRefundedException,
)
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.test.factories import TransactionFactory, mock_payment_method
from uobtheatre.productions.models import Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.exceptions import GQLException
from uobtheatre.utils.test_utils import ticket_dict_list_dict_gen, ticket_list_dict_gen
from uobtheatre.venues.test.factories import SeatFactory, SeatGroupFactory, VenueFactory


@pytest.mark.django_db
def test_is_valid_single_discount():
    booking = BookingFactory()
    discount = DiscountFactory()
    discount.performance = booking.performance

    # Create a discount that requires one student
    concession_type_student = ConcessionTypeFactory(name="Student")
    DiscountRequirementFactory(
        concession_type=concession_type_student, number=1, discount=discount
    )

    # When no seats are booked assert this discount cannot be applied
    assert not booking.is_valid_discount_combination(DiscountCombination((discount,)))

    # When one non student seat is booked assert this discount cannot be applied
    TicketFactory(booking=booking)
    assert not booking.is_valid_discount_combination(DiscountCombination((discount,)))

    # When a student seat is booked assert this discount can be applied
    TicketFactory(booking=booking, concession_type=concession_type_student)
    assert booking.is_valid_discount_combination(DiscountCombination((discount,)))


@pytest.mark.django_db
def test_is_valid_multi_discount():
    booking = BookingFactory()
    discount = DiscountFactory()
    discount.performance = booking.performance

    # Create a discount that requires one student
    concession_type_student = ConcessionTypeFactory(name="Student")
    concession_type_adult = ConcessionTypeFactory(name="Adult")
    DiscountRequirementFactory(
        concession_type=concession_type_student, number=2, discount=discount
    )
    DiscountRequirementFactory(
        concession_type=concession_type_adult, number=1, discount=discount
    )

    # When no seats are booked assert this discount cannot be applied
    assert not booking.is_valid_discount_combination(DiscountCombination((discount,)))

    # When only one student seat is booked and two adult seat assert this
    # discount cannot be applied
    TicketFactory(booking=booking, concession_type=concession_type_adult)
    TicketFactory(booking=booking, concession_type=concession_type_adult)
    TicketFactory(booking=booking, concession_type=concession_type_student)
    assert not booking.is_valid_discount_combination(DiscountCombination((discount,)))

    # When a student seat is booked assert this discount can be applied
    TicketFactory(booking=booking, concession_type=concession_type_student)
    assert booking.is_valid_discount_combination(DiscountCombination((discount,)))


@pytest.mark.django_db
def test_get_valid_discounts():
    performance = PerformanceFactory()
    booking = BookingFactory(performance=performance)

    # Create some concession types
    concession_type_student = ConcessionTypeFactory(name="Student")
    concession_type_adult = ConcessionTypeFactory(name="Adult")

    # Create a family discount - 1 student ticket and 2 adults required
    discount_family = DiscountFactory(name="Family", percentage=0.2)
    discount_family.performances.set([performance])
    DiscountRequirementFactory(
        concession_type=concession_type_student, number=1, discount=discount_family
    )
    DiscountRequirementFactory(
        concession_type=concession_type_adult, number=2, discount=discount_family
    )

    # Create a student discount - 1 student ticket required
    discount_student = DiscountFactory(name="Student", percentage=0.2)
    discount_student.performances.set([performance])
    DiscountRequirementFactory(
        concession_type=concession_type_student, number=1, discount=discount_student
    )

    # Check that both discounts have been created
    assert performance.discounts.all().count() == 2

    # When no seats are booked there are no valid discounts
    assert booking.get_valid_discounts() == []

    # When one student seat is booked the student discount should be available
    TicketFactory(booking=booking, concession_type=concession_type_student)
    assert booking.get_valid_discounts() == [DiscountCombination((discount_student,))]

    TicketFactory(booking=booking, concession_type=concession_type_adult)
    TicketFactory(booking=booking, concession_type=concession_type_adult)
    assert set(
        map(lambda d: d.discount_combination, booking.get_valid_discounts())
    ) == set(
        [
            (discount_student,),
            (discount_family,),
        ]
    )

    TicketFactory(booking=booking, concession_type=concession_type_student)
    assert set(
        map(lambda d: d.discount_combination, booking.get_valid_discounts())
    ) == set(
        [
            (discount_family, discount_student),
            (discount_student, discount_family),
            (discount_family,),
            (discount_student,),
            (discount_student, discount_student),
        ]
    )


@pytest.mark.django_db
def test_get_price():
    performance = PerformanceFactory()
    booking = BookingFactory(performance=performance)
    assert booking.get_price() == 0

    # Set seat type price for performance
    performance_seat_group = PerformanceSeatingFactory(
        performance=performance, price=500
    )

    # Create a seat booking
    TicketFactory(booking=booking, seat_group=performance_seat_group.seat_group)

    assert booking.get_price() == 500

    TicketFactory(booking=booking, seat_group=performance_seat_group.seat_group)
    assert booking.get_price() == 1000

    performance_seat_group_2 = PerformanceSeatingFactory(
        performance=performance, price=100
    )
    TicketFactory(booking=booking, seat_group=performance_seat_group_2.seat_group)
    assert booking.get_price() == 1100


@pytest.mark.django_db
def test_ticket_price():
    performance = PerformanceFactory()
    booking = BookingFactory(performance=performance)

    # Set seat type price for performance
    performance_seat_group = PerformanceSeatingFactory(performance=performance)

    # Create a seat booking
    ticket = TicketFactory(
        booking=booking, seat_group=performance_seat_group.seat_group
    )

    assert ticket.seat_price() == performance_seat_group.price


@pytest.mark.django_db
@pytest.mark.parametrize(
    "discount_amount, number_req, seat_group_price, discount_price",
    [
        (0.2, 1, 1200, 960),
        (0.3, 1, 1300, 910),
        (0, 1, 1200, 1200),
        (0.2, 2, 1200, 1200),
    ],
)
def test_ticket_discounted_price(
    discount_amount, number_req, seat_group_price, discount_price
):
    performance = PerformanceFactory()
    booking = BookingFactory(performance=performance)

    test_concession_type = ConcessionTypeFactory(name="Student")
    discount_student = DiscountFactory(name="Student", percentage=discount_amount)
    discount_student.performances.set([performance])
    DiscountRequirementFactory(
        concession_type=test_concession_type,
        number=number_req,
        discount=discount_student,
    )
    # Set seat type price for performance
    performance_seat_group = PerformanceSeatingFactory(
        performance=performance, price=seat_group_price
    )

    # Create a seat booking
    ticket = TicketFactory(
        booking=booking,
        concession_type=test_concession_type,
        seat_group=performance_seat_group.seat_group,
    )

    assert ticket.discounted_price() == discount_price
    assert ticket.discounted_price(performance.single_discounts_map) == discount_price


@pytest.mark.django_db
def test_ticket_discount_with_discount_map():
    performance = PerformanceFactory()

    booking = BookingFactory(performance=performance)
    performance_seat_group = PerformanceSeatingFactory(
        performance=performance, price=1000
    )

    concession_type_1 = ConcessionTypeFactory(name="student")
    concession_type_2 = ConcessionTypeFactory(name="child")

    ticket_1 = TicketFactory(
        booking=booking,
        concession_type=concession_type_1,
        seat_group=performance_seat_group.seat_group,
    )

    ticket_2 = TicketFactory(
        booking=booking,
        concession_type=concession_type_2,
        seat_group=performance_seat_group.seat_group,
    )

    single_discounts_map = {
        concession_type_1: 0.2,
    }

    assert ticket_1.discounted_price(single_discounts_map) == 800
    assert ticket_2.discounted_price(single_discounts_map) == 1000


@pytest.mark.django_db
def test_single_discounts_map():
    performance = PerformanceFactory()

    concession_type_1 = ConcessionTypeFactory()
    concession_type_2 = ConcessionTypeFactory()
    concession_type_3 = ConcessionTypeFactory()

    concession_type_1 = ConcessionTypeFactory()
    discount_1 = DiscountFactory(name="Family")
    DiscountRequirementFactory(
        discount=discount_1, number=1, concession_type=concession_type_1
    )

    discount_2 = DiscountFactory(name="Student")
    DiscountRequirementFactory(
        discount=discount_2, number=1, concession_type=concession_type_2
    )

    discount_3 = DiscountFactory(name="Student")
    DiscountRequirementFactory(
        discount=discount_3, number=1, concession_type=concession_type_2
    )
    DiscountRequirementFactory(
        discount=discount_3, number=1, concession_type=concession_type_3
    )

    discount_1.performances.set([performance])
    discount_2.performances.set([performance])
    discount_3.performances.set([performance])

    booking = BookingFactory(performance=performance)

    assert booking.single_discounts_map == performance.single_discounts_map
    assert performance.single_discounts_map == {
        concession_type_1: discount_1.percentage,
        concession_type_2: discount_2.percentage,
    }


@pytest.mark.django_db
def test_get_price_with_discount_combination():
    venue = VenueFactory()
    performance = PerformanceFactory(venue=venue)
    booking = BookingFactory(performance=performance)

    concession_type_student = ConcessionTypeFactory(name="Student")
    concession_type_adult = ConcessionTypeFactory(name="Adult")

    # Set seat type price for performance
    seating = PerformanceSeatingFactory(performance=performance)

    # Create a seat booking
    TicketFactory(
        booking=booking,
        seat_group=seating.seat_group,
        concession_type=concession_type_student,
    )
    TicketFactory(
        booking=booking,
        seat_group=seating.seat_group,
        concession_type=concession_type_student,
    )

    # Check price without discount
    assert booking.get_price() == seating.price * 2

    discount_student = DiscountFactory(name="Student", percentage=0.2)
    discount_student.performances.set([performance])
    DiscountRequirementFactory(
        concession_type=concession_type_student, number=1, discount=discount_student
    )
    discount_combination = DiscountCombination((discount_student,))
    assert discount_student.percentage == 0.2
    assert booking.get_price_with_discount_combination(
        discount_combination
    ) == math.ceil((seating.price * (1 - discount_student.percentage)) + seating.price)

    discount_family = DiscountFactory(name="Family", percentage=0.2)
    discount_family.performances.set([performance])
    DiscountRequirementFactory(
        concession_type=concession_type_student, number=1, discount=discount_family
    )
    DiscountRequirementFactory(
        concession_type=concession_type_adult, number=2, discount=discount_family
    )

    TicketFactory(
        booking=booking,
        seat_group=seating.seat_group,
        concession_type=concession_type_adult,
    )
    TicketFactory(
        booking=booking,
        seat_group=seating.seat_group,
        concession_type=concession_type_adult,
    )

    discount_combination = DiscountCombination((discount_student, discount_family))
    assert (
        booking.get_price_with_discount_combination(discount_combination)
        # Price is calculated a ticket level so each ticket price should be rounded individually
        == math.ceil(seating.price * (1 - discount_student.percentage))
        + (3 * math.ceil(seating.price * (1 - discount_family.percentage)))
    )


@pytest.mark.django_db
def test_get_best_discount_combination():
    performance = PerformanceFactory()
    booking = BookingFactory(performance=performance)
    venue = VenueFactory()

    # Create some concession types
    concession_type_student = ConcessionTypeFactory(name="Student")
    concession_type_adult = ConcessionTypeFactory(name="Adult")

    seat_group = SeatGroupFactory(venue=venue)

    # Set seat type price for performance
    PerformanceSeatingFactory(performance=performance, seat_group=seat_group)

    # Create a family discount - 1 student ticket and 2 adults required
    discount_family = DiscountFactory(name="Family", percentage=0.2)
    discount_family.performances.set([performance])
    DiscountRequirementFactory(
        concession_type=concession_type_student, number=1, discount=discount_family
    )
    DiscountRequirementFactory(
        concession_type=concession_type_adult, number=2, discount=discount_family
    )

    # Create a student discount - 1 student ticket required
    discount_student = DiscountFactory(name="Student", percentage=0.2)
    discount_student.performances.set([performance])
    DiscountRequirementFactory(
        concession_type=concession_type_student, number=1, discount=discount_student
    )

    TicketFactory(
        booking=booking, concession_type=concession_type_student, seat_group=seat_group
    )
    TicketFactory(
        booking=booking, concession_type=concession_type_adult, seat_group=seat_group
    )
    TicketFactory(
        booking=booking, concession_type=concession_type_adult, seat_group=seat_group
    )
    TicketFactory(
        booking=booking, concession_type=concession_type_student, seat_group=seat_group
    )

    assert booking.performance.discounts.count() == 2

    assert booking.performance.discounts.first().name == "Family"
    assert booking.performance.discounts.first().percentage == 0.2
    assert set(booking.get_best_discount_combination().discount_combination) == set(
        (
            discount_student,
            discount_family,
        )
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "students, adults, is_single",
    [
        (1, 0, True),
        (0, 1, True),
        (2, 1, False),
        (0, 0, False),
    ],
)
def test_is_single_discount(students, adults, is_single):
    # Create a discount
    discount = DiscountFactory(name="Family")
    DiscountRequirementFactory(number=students, discount=discount)
    DiscountRequirementFactory(number=adults, discount=discount)

    assert discount.is_single_discount() == is_single


@pytest.mark.django_db
def test_str_discount():
    discount = DiscountFactory(percentage=0.12, name="student")
    assert str(discount) == "12.0% off for student"


@pytest.mark.django_db
def test_str_booking():
    booking = BookingFactory()
    assert str(booking) == str(booking.reference)


@pytest.mark.django_db
def test_str_concession_type():
    concession_type = ConcessionTypeFactory()
    assert str(concession_type) == concession_type.name


@pytest.mark.django_db
def test_percentage_misc_cost_value():
    misc_cost = PercentageMiscCostFactory(percentage=0.2)

    # Create a booking costing £12
    booking = BookingFactory()
    psg = PerformanceSeatingFactory(performance=booking.performance, price=1200)
    TicketFactory(booking=booking, seat_group=psg.seat_group)

    assert misc_cost.get_value(booking) == 240


@pytest.mark.django_db
def test_misc_costs_value():
    ValueMiscCostFactory(value=200)
    PercentageMiscCostFactory(percentage=0.1)

    # Create a booking costing £12
    booking = BookingFactory()
    psg = PerformanceSeatingFactory(performance=booking.performance, price=1200)
    TicketFactory(booking=booking, seat_group=psg.seat_group)
    assert booking.misc_costs_value == 320


@pytest.mark.django_db
def test_subtotal_with_group_discounts():
    performance = PerformanceFactory()
    group_discount = DiscountFactory()
    group_discount.performances.set([performance])
    DiscountRequirementFactory(discount=group_discount)
    DiscountRequirementFactory(discount=group_discount)
    booking = BookingFactory(performance=performance)

    assert booking.subtotal == booking.get_best_discount_combination_with_price()[1]


@pytest.mark.django_db
def test_total():
    ValueMiscCostFactory(value=200)
    PercentageMiscCostFactory(percentage=0.1)

    # Create a booking costing £12
    booking = BookingFactory()
    psg = PerformanceSeatingFactory(performance=booking.performance, price=1200)
    ticket = TicketFactory(booking=booking, seat_group=psg.seat_group)
    assert ticket.booking.total == 1520


@pytest.mark.django_db
@pytest.mark.parametrize(
    "admin_discount, expected_price, expected_misc_costs_value",
    [(0.2, 1256, 296), (1, 0, 0)],
)
def test_total_with_admin_discount(
    admin_discount, expected_price, expected_misc_costs_value
):
    ValueMiscCostFactory(value=200)
    PercentageMiscCostFactory(percentage=0.1)

    # Create a booking costing £12
    booking = BookingFactory(admin_discount_percentage=admin_discount)
    psg = PerformanceSeatingFactory(performance=booking.performance, price=1200)
    ticket = TicketFactory(booking=booking, seat_group=psg.seat_group)
    assert booking.misc_costs_value == expected_misc_costs_value
    assert ticket.booking.total == expected_price


@pytest.mark.django_db
def test_draft_uniqueness():
    args = {
        "user": UserFactory(),
        "performance": PerformanceFactory(),
        "status": Payable.Status.IN_PROGRESS,
    }

    # Check that can make more bookings that are no in_progress
    BookingFactory(
        status=Payable.Status.PAID,
        performance=args["performance"],
        user=args["user"],
    )

    # Cannot create 2 booking with in_progress status
    BookingFactory(**args)
    with pytest.raises(IntegrityError):
        BookingFactory(**args)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value, percentage, error",
    [(None, None, True), (None, 1, False), (1, None, False), (1, 1, True)],
)
def test_misc_cost_constraints(value, percentage, error):
    """
    Check a when creating a misc cost you must have either a value or a
    percentage but not both.
    """
    args = {
        "name": "Some misc cost",
        "value": value,
        "percentage": percentage,
    }

    if not error:
        MiscCost.objects.create(**args)
    else:
        with pytest.raises(IntegrityError):
            MiscCost.objects.create(**args)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "existing_list, new_list, add_list, delete_list, expected_total_number_of_tickets",
    [
        # SAME, SAME, null, null  - SAME
        (
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 2,
                },
            ],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 2,
                },
            ],
            [],
            [],
            2,
        ),
        # 1&2, 1, null, 2 - DELETE 1
        (
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 2,
                },
            ],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
            ],
            [],
            [
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 2,
                }
            ],
            1,
        ),
        # 1, 1&2, 2, null - ADD 1
        (
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
            ],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
            ],
            [
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                }
            ],
            [],
            2,
        ),
        # 1&2, null, null, 1&2 - DELETE ALL
        (
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 2,
                },
            ],
            [],
            [],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 2,
                },
            ],
            0,
        ),
        # null, 1&2, 1&2, null - ADD ALL
        (
            [],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
            ],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
            ],
            [],
            2,
        ),
        # 1, 2, 2, 1 - SWAP
        (
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
            ],
            [
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                }
            ],
            [
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                }
            ],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
            ],
            1,
        ),
    ],
)
def test_booking_ticket_diff(
    existing_list, new_list, add_list, delete_list, expected_total_number_of_tickets
):
    SeatGroupFactory(id=1)
    SeatGroupFactory(id=2)
    ConcessionTypeFactory(id=1)
    ConcessionTypeFactory(id=2)
    SeatFactory(id=1)
    SeatFactory(id=2)

    booking = BookingFactory()

    _ = [TicketFactory(booking=booking, **ticket) for ticket in existing_list]
    new_tickets = [Ticket(**ticket) for ticket in new_list]
    add_tickets = [Ticket(**ticket) for ticket in add_list]
    delete_tickets = [Ticket(**ticket) for ticket in delete_list]

    add_tickets, delete_tickets, total_number_of_tickets = booking.get_ticket_diff(
        new_tickets
    )
    expected_add_tickets, expected_delete_tickets = map(
        ticket_dict_list_dict_gen,
        [
            add_list,
            delete_list,
        ],
    )
    actual_add_tickets, actual_delete_tickets = map(
        ticket_list_dict_gen,
        [
            add_tickets,
            delete_tickets,
        ],
    )
    assert expected_add_tickets == actual_add_tickets
    assert expected_delete_tickets == actual_delete_tickets
    assert total_number_of_tickets == expected_total_number_of_tickets


@pytest.mark.django_db
def test_booking_pay_with_payment():
    """
    When the payment_method pay return a payment assert the booking is marked
    as paid.
    """

    payment_method = mock_payment_method()
    booking = BookingFactory(status=Payable.Status.IN_PROGRESS)

    booking.pay(payment_method)  # type: ignore

    assert booking.status == Payable.Status.PAID


@pytest.mark.django_db
def test_booking_pay():
    """
    Raise exception when trying to pay for an expired booking.
    """

    payment_method = mock_payment_method()
    booking = BookingFactory(status=Payable.Status.IN_PROGRESS)

    with patch(
        "uobtheatre.bookings.models.Booking.is_reservation_expired",
        new_callable=PropertyMock(return_value=False),
    ):
        booking.pay(payment_method)  # type: ignore
    payment_method.pay.assert_called_once()


@pytest.mark.django_db
def test_booking_pay_expired_booking():
    payment_method = mock_payment_method()
    booking = BookingFactory(status=Payable.Status.IN_PROGRESS)

    with patch(
        "uobtheatre.bookings.models.Booking.is_reservation_expired",
        new_callable=PropertyMock(return_value=True),
    ), pytest.raises(
        CantBePaidForException,
        match="This booking has expired. Please create a new booking",
    ):
        booking.pay(payment_method)

    payment_method.pay.assert_not_called()


@pytest.mark.django_db
def test_ticket_check_in():
    """
    Test ticket check in method
    """
    mock_ticket_check_in_time = datetime.datetime(2020, 1, 2, 23, 45)
    user = UserFactory()

    ticket_unchecked = TicketFactory(set_checked_in=False)
    assert not ticket_unchecked.checked_in

    with patch.object(timezone, "now", return_value=mock_ticket_check_in_time) as _:
        ticket_unchecked.check_in(user=user)

    assert ticket_unchecked.checked_in
    assert ticket_unchecked.checked_in_at == mock_ticket_check_in_time
    assert ticket_unchecked.checked_in_by == user


@pytest.mark.django_db
def test_ticket_check_in_fails_if_ticket_already_checked_in():
    ticket_checked = TicketFactory(set_checked_in=True)
    assert ticket_checked.checked_in

    with pytest.raises(GQLException) as exception:
        ticket_checked.check_in(user=UserFactory())
    assert (
        exception.value.message
        == f"Ticket of id {ticket_checked.id} is already checked-in."
    )


@pytest.mark.django_db
def test_ticket_uncheck_in():
    ticket_checked = TicketFactory(set_checked_in=True)
    assert ticket_checked.checked_in

    ticket_checked.uncheck_in()
    assert not ticket_checked.checked_in
    assert Ticket.objects.first().checked_in_at is None
    assert ticket_checked.checked_in_by is None


@pytest.mark.django_db
def test_ticket_uncheck_in_fails_if_ticket_not_checked_in():
    ticket_unchecked = TicketFactory(set_checked_in=False)
    assert not ticket_unchecked.checked_in

    with pytest.raises(GQLException) as exception:
        ticket_unchecked.uncheck_in()
    assert (
        exception.value.message
        == f"Ticket of id {ticket_unchecked.id} cannot be un-checked in as it is not checked-in."
    )


@pytest.mark.django_db
def test_filter_order_by_checked_in():
    """
    Filter by booking tickets checked in
    Order by booking tickets checked in
    """
    # No tickets booking
    booking_no_tickets = BookingFactory()

    # None checked in
    booking_none = BookingFactory()
    TicketFactory(booking=booking_none)
    TicketFactory(booking=booking_none)

    # Some checked in
    booking_some = BookingFactory()
    TicketFactory(booking=booking_some, set_checked_in=True)
    TicketFactory(booking=booking_some)

    # All checked in
    booking_all = BookingFactory()
    TicketFactory(booking=booking_all, set_checked_in=True)
    TicketFactory(booking=booking_all, set_checked_in=True)

    assert {
        (booking.reference, booking.proportion)
        for booking in Booking.objects.annotate_checked_in_proportion()
    } == {
        (booking_no_tickets.reference, 0),
        (booking_none.reference, 0),
        (booking_some.reference, 0.5),
        (booking_all.reference, 1),
    }

    assert set(Booking.objects.checked_in()) == {booking_all}
    assert set(Booking.objects.checked_in(True)) == {booking_all}
    assert set(Booking.objects.checked_in(False)) == {booking_none, booking_some}


@pytest.mark.django_db
def test_filter_by_active():
    """
    Filter active bookings
        Active - performance end date is in the future
        Not active - performance end date in the past
    """

    now = timezone.now()

    production = ProductionFactory()

    performance_future = PerformanceFactory(
        production=production, end=now + datetime.timedelta(days=2)
    )
    performance_past = PerformanceFactory(
        production=production, end=now + datetime.timedelta(days=-2)
    )

    booking_future = BookingFactory(performance=performance_future)
    booking_past = BookingFactory(performance=performance_past)

    assert list(Booking.objects.active()) == [booking_future]
    assert list(Booking.objects.active(True)) == [booking_future]
    assert list(Booking.objects.active(False)) == [booking_past]


@pytest.mark.django_db
def test_booking_expiration():
    unexpired_booking = BookingFactory(status=Payable.Status.IN_PROGRESS)

    expired_booking = BookingFactory(
        status=Payable.Status.IN_PROGRESS,
        expires_at=timezone.now() - datetime.timedelta(minutes=16),
    )

    assert unexpired_booking.expires_at > timezone.now() + datetime.timedelta(
        minutes=14
    )
    assert unexpired_booking.expires_at < timezone.now() + datetime.timedelta(
        minutes=16
    )

    assert not unexpired_booking.is_reservation_expired
    assert expired_booking.is_reservation_expired

    expired_booking.status = Payable.Status.PAID
    expired_booking.save()
    assert not expired_booking.is_reservation_expired

    expired_booking.status = Payable.Status.CANCELLED
    expired_booking.save()
    assert not expired_booking.is_reservation_expired


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_refunded,status,production_status,expected",
    [
        (False, Payable.Status.PAID, Production.Status.PUBLISHED, True),
        (False, Payable.Status.PAID, Production.Status.PENDING, True),
        (True, Payable.Status.PAID, Production.Status.PUBLISHED, False),
        (False, Payable.Status.CANCELLED, Production.Status.PUBLISHED, True),
        (True, Payable.Status.CANCELLED, Production.Status.PUBLISHED, False),
        (False, Payable.Status.PAID, Production.Status.CLOSED, False),
    ],
)
def test_booking_can_be_refunded(is_refunded, status, production_status, expected):
    production = ProductionFactory(status=production_status)

    with patch(
        "uobtheatre.bookings.models.Booking.is_refunded",
        new_callable=PropertyMock(return_value=is_refunded),
    ):
        booking = BookingFactory(
            performance=PerformanceFactory(production=production), status=status
        )
        TransactionFactory(pay_object=booking)
        assert booking.can_be_refunded == expected

        if expected:
            assert booking.validate_cant_be_refunded() is None
        else:
            assert (
                isinstance(booking.validate_cant_be_refunded(), CantBeRefundedException)
                is True
            )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "with_payment,with_accessibility",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_complete(with_payment, with_accessibility):
    booking = BookingFactory(
        status=Payable.Status.IN_PROGRESS,
        accessibility_info=("Something" if with_accessibility else None),
    )
    with patch(
        "uobtheatre.bookings.emails.send_booking_confirmation_email"
    ) as mock_send_email, patch(
        "uobtheatre.bookings.emails.send_booking_accessibility_info_email"
    ) as mock_send_accessibility_email:
        kwargs = {}
        if with_payment:
            kwargs["payment"] = TransactionFactory()
        booking.complete(**kwargs)
        mock_send_email.assert_called_once()

        if with_accessibility:
            mock_send_accessibility_email.assert_called_once()
        else:
            mock_send_accessibility_email.assert_not_called()

    booking.refresh_from_db()
    assert booking.status == Payable.Status.PAID


@pytest.mark.django_db
def test_web_tickets_path_property():
    booking = BookingFactory(reference="abcd1234")
    ticket_ids = [
        # Get URL safe global ids
        quote_plus((to_global_id("TicketNode", ticket.id)))
        for ticket in [TicketFactory(booking=booking, id=i) for i in range(3)]
    ]
    performance_id = quote_plus(to_global_id("PerformanceNode", booking.performance.id))
    assert (
        booking.web_tickets_path
        == f"/user/booking/abcd1234/tickets?performanceID={performance_id}&ticketID={ticket_ids[0]}&ticketID={ticket_ids[1]}&ticketID={ticket_ids[2]}"
    )


@pytest.mark.django_db
def test_booking_display_name():
    production = ProductionFactory(name="My Production")
    performance = PerformanceFactory(
        production=production,
        start=datetime.datetime(2022, 1, 14, 10, 0, tzinfo=pytz.UTC),
    )
    booking = BookingFactory(performance=performance, reference="abcd")

    assert (
        booking.display_name
        == "Booking Ref. abcd for performance of my production at 10:00 on 14/01/2022"
    )


@pytest.mark.django_db
def test_booking_clone():
    # Create a booking
    booking = BookingFactory()
    assert Booking.objects.count() == 1

    # Clone it
    booking_clone = booking.clone()
    assert Booking.objects.count() == 1

    # Check a unique booking reference is assigned
    assert booking_clone.reference is not None
    assert booking_clone.reference != booking.reference
