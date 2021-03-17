import pytest
from django.db.utils import IntegrityError

from uobtheatre.bookings.models import (
    Booking,
    Discount,
    DiscountCombination,
    DiscountRequirement,
    MiscCost,
    Ticket,
    combinations,
)
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
    PercentageMiscCostFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.payments.models import Payment
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.exceptions import SquareException
from uobtheatre.venues.test.factories import SeatFactory, SeatGroupFactory, VenueFactory


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
def test_is_valid_single_discount():
    booking = BookingFactory()
    discount = DiscountFactory()
    discount.performance = booking.performance

    # Create a discount that requires one student
    concession_type_student = ConcessionTypeFactory(name="Student")
    discount_requirements = DiscountRequirementFactory(
        concession_type=concession_type_student, number=1, discount=discount
    )

    # When no seats are booked assert this discount cannot be applied
    assert not booking.is_valid_discount_combination(DiscountCombination((discount,)))

    # When one non student seat is booked assert this discount cannot be applied
    seat_booking = TicketFactory(booking=booking)
    assert not booking.is_valid_discount_combination(DiscountCombination((discount,)))

    # When a student seat is booked assert this discount can be applied
    seat_booking = TicketFactory(
        booking=booking, concession_type=concession_type_student
    )
    assert booking.is_valid_discount_combination(DiscountCombination((discount,)))


@pytest.mark.django_db
def test_is_valid_multi_discount():
    booking = BookingFactory()
    discount = DiscountFactory()
    discount.performance = booking.performance

    # Create a discount that requires one student
    concession_type_student = ConcessionTypeFactory(name="Student")
    concession_type_adult = ConcessionTypeFactory(name="Adult")
    discount_requirements = DiscountRequirementFactory(
        concession_type=concession_type_student, number=2, discount=discount
    )
    discount_requirements = DiscountRequirementFactory(
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

    # Set seat type price for performance
    performance_seat_group = PerformanceSeatingFactory(performance=performance)

    # Create a seat booking
    TicketFactory(booking=booking, seat_group=performance_seat_group.seat_group)

    assert booking.get_price() == performance_seat_group.price

    TicketFactory(booking=booking, seat_group=performance_seat_group.seat_group)
    assert booking.get_price() == performance_seat_group.price * 2

    performance_seat_group_2 = PerformanceSeatingFactory(performance=performance)
    TicketFactory(booking=booking, seat_group=performance_seat_group_2.seat_group)
    assert (
        booking.get_price()
        == performance_seat_group.price * 2 + performance_seat_group_2.price
    )


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
    assert round(
        booking.get_price_with_discount_combination(discount_combination)
    ) == round((seating.price * (1 - discount_student.percentage)) + seating.price)

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
    assert round(
        booking.get_price_with_discount_combination(discount_combination)
    ) == round(
        (seating.price * (1 - discount_student.percentage))
        + (seating.price * 3 * (1 - discount_family.percentage))
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
    ticket = TicketFactory(booking=booking, seat_group=psg.seat_group)

    assert misc_cost.get_value(booking) == 240


@pytest.mark.django_db
def test_misc_costs_value():
    ValueMiscCostFactory(value=200)
    PercentageMiscCostFactory(percentage=0.1)

    # Create a booking costing £12
    booking = BookingFactory()
    psg = PerformanceSeatingFactory(performance=booking.performance, price=1200)
    ticket = TicketFactory(booking=booking, seat_group=psg.seat_group)
    assert booking.misc_costs_value() == 320


@pytest.mark.django_db
def test_total():
    ValueMiscCostFactory(value=200)
    PercentageMiscCostFactory(percentage=0.1)

    # Create a booking costing £12
    booking = BookingFactory()
    psg = PerformanceSeatingFactory(performance=booking.performance, price=1200)
    ticket = TicketFactory(booking=booking, seat_group=psg.seat_group)
    assert ticket.booking.total() == 1520


@pytest.mark.django_db
def test_draft_uniqueness():
    args = {
        "user": UserFactory(),
        "performance": PerformanceFactory(),
        "status": Booking.BookingStatus.IN_PROGRESS,
    }

    # Check that can make more bookings that are no in_progress
    BookingFactory(
        status=Booking.BookingStatus.PAID,
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
def test_create_booking_serializer_seat_group_is_from_performance_validation():
    user = UserFactory(id=1)
    performance = PerformanceFactory(id=1, capacity=10)
    sg_1 = SeatGroupFactory(id=1)
    sg_2 = SeatGroupFactory(id=2)
    ConcessionTypeFactory(id=1)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "existingList, newList, addList, deleteList",
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
        ),
    ],
)
def test_booking_ticket_diff(existingList, newList, addList, deleteList):
    SeatGroupFactory(id=1)
    SeatGroupFactory(id=2)
    ConcessionTypeFactory(id=1)
    ConcessionTypeFactory(id=2)
    SeatFactory(id=1)
    SeatFactory(id=2)

    booking = BookingFactory()

    _ = [TicketFactory(booking=booking, **ticket) for ticket in existingList]
    newTickets = [Ticket(**ticket) for ticket in newList]
    addTickets = [Ticket(**ticket) for ticket in addList]
    deleteTickets = [Ticket(**ticket) for ticket in deleteList]

    assert booking.get_ticket_diff(newTickets) == (addTickets, deleteTickets)


@pytest.mark.django_db
def test_booking_pay_failure(mock_square):
    """
    Test paying a booking with square
    """
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    psg = PerformanceSeatingFactory(performance=booking.performance)
    ticket = TicketFactory(booking=booking, seat_group=psg.seat_group)

    mock_square.reason_phrase = "Some phrase"
    mock_square.status_code = 400
    mock_square.success = False

    with pytest.raises(SquareException):
        booking.pay("nonce")

    # Assert the booking is not paid
    assert booking.status == Booking.BookingStatus.IN_PROGRESS

    # Assert no payments are created
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_booking_pay_success(mock_square):
    """
    Test paying a booking with square
    """
    booking = BookingFactory()
    psg = PerformanceSeatingFactory(performance=booking.performance)
    ticket = TicketFactory(booking=booking, seat_group=psg.seat_group)

    mock_square.success = True
    mock_square.body = {
        "payment": {
            "id": "abc",
            "card_details": {
                "card": {
                    "card_brand": "MASTERCARD",
                    "last_4": "1234",
                }
            },
            "amount_money": {
                "currency": "GBP",
                "amount": 0,
            },
        }
    }

    booking.pay("nonce")

    assert booking.status == Booking.BookingStatus.PAID
    # Assert a payment of the correct type is created
    payment = booking.payments.first()
    assert payment.pay_object == booking
    assert payment.value == 0
    assert payment.currency == "GBP"
    assert payment.card_brand == "MASTERCARD"
    assert payment.last_4 == "1234"
    assert payment.provider_payment_id == "abc"
    assert payment.provider == Payment.PaymentProvider.SQUARE_ONLINE
    assert payment.type == Payment.PaymentType.PURCHASE


@pytest.mark.django_db
@pytest.mark.square_integration
def test_booking_pay_integration():
    """
    Test paying a booking with square
    """
    booking = BookingFactory()
    psg = PerformanceSeatingFactory(performance=booking.performance)
    TicketFactory(booking=booking, seat_group=psg.seat_group)

    booking.pay("cnon:card-nonce-ok")

    assert booking.status == Booking.BookingStatus.PAID
    # Assert a payment of the correct type is created
    payment = booking.payments.first()
    assert payment.pay_object == booking
    assert payment.value == booking.total()
    assert payment.currency == "GBP"
    assert isinstance(payment.card_brand, str)
    assert isinstance(payment.last_4, str) and len(payment.last_4) == 4
    assert isinstance(payment.provider_payment_id, str)
    assert payment.provider == Payment.PaymentProvider.SQUARE_ONLINE
    assert payment.type, Payment.PaymentType.PURCHASE


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ticket1, ticket2, eq",
    [
        (
            {
                "seat_group_id": 1,
                "concession_type_id": 1,
                "seat_id": 1,
            },
            {
                "seat_group_id": 1,
                "concession_type_id": 1,
                "seat_id": 1,
            },
            True,
        ),
        (
            # Check not eq with different seat_group
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
            False,
        ),
        (
            # Check not eq with different concession_type
            {
                "seat_group_id": 1,
                "concession_type_id": 1,
                "seat_id": 1,
            },
            {
                "seat_group_id": 1,
                "concession_type_id": 2,
                "seat_id": 1,
            },
            False,
        ),
        (
            # Check not eq with different seat
            {
                "seat_group_id": 1,
                "concession_type_id": 1,
                "seat_id": 2,
            },
            {
                "seat_group_id": 1,
                "concession_type_id": 1,
                "seat_id": 1,
            },
            False,
        ),
    ],
)
def test_ticket_eq(ticket1, ticket2, eq):
    SeatGroupFactory(id=1)
    SeatGroupFactory(id=2)
    ConcessionTypeFactory(id=1)
    ConcessionTypeFactory(id=2)
    SeatFactory(id=1)
    SeatFactory(id=2)

    assert (Ticket(**ticket1) == Ticket(**ticket2)) == eq
