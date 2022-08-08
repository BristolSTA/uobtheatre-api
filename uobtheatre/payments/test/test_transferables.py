# pylint: disable=too-many-lines
import datetime
from unittest.mock import PropertyMock, patch

import pytest
import pytz

from uobtheatre.bookings.exceptions import (
    BookingTransferPerformanceUnchangedException,
    BookingTransferToDifferentProductionException,
)
from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
)
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
)
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.productions.exceptions import (
    NotBookableException,
    NotEnoughCapacityException,
)
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_transfered_from_chain():
    booking_3 = BookingFactory()
    booking_2 = BookingFactory(transfered_from=booking_3)
    booking_1 = BookingFactory(transfered_from=booking_2)

    booking_4 = BookingFactory()

    assert booking_1.transfered_from_chain == [booking_2, booking_3]
    assert booking_2.transfered_from_chain == [booking_3]
    assert booking_3.transfered_from_chain == []
    assert booking_4.transfered_from_chain == []


@pytest.mark.django_db
def test_transfered_to():
    booking_3 = BookingFactory()
    booking_2 = BookingFactory(transfered_from=booking_3)
    booking_1 = BookingFactory(transfered_from=booking_2)

    booking_4 = BookingFactory()

    assert booking_1.transfered_to is None
    assert booking_4.transfered_to is None
    assert booking_2.transfered_to == booking_1
    assert booking_3.transfered_to == booking_2


@pytest.mark.django_db
def test_transfer_reduction():
    booking = BookingFactory()

    # Create some bookings which this booking is transfered from
    transfered_from_bookings = [BookingFactory() for _ in range(3)]

    with patch(
        "uobtheatre.bookings.models.Booking.transfered_from_chain",
        new_callable=PropertyMock,
    ) as mock:
        mock.return_value = transfered_from_bookings
        reduction_value = booking.transfer_reduction

        # With no payments it should be 0
        assert Transaction.objects.count() == 0
        assert reduction_value == 0

        # Add transactions to the bookings
        TransactionFactory(
            pay_object=transfered_from_bookings[0],
            value=100,
            app_fee=0,
            provider_fee=0,
            status=Transaction.Status.COMPLETED,
            type=Transaction.Type.PAYMENT,
        )
        TransactionFactory(
            pay_object=transfered_from_bookings[2],
            value=150,
            app_fee=10,
            provider_fee=2,
            status=Transaction.Status.COMPLETED,
            type=Transaction.Type.PAYMENT,
        )

        # Add excluded transcation to ensure its not counted
        TransactionFactory(
            pay_object=transfered_from_bookings[2],
            value=150,
            app_fee=10,
            provider_fee=2,
            status=Transaction.Status.PENDING,
            type=Transaction.Type.PAYMENT,
        )

        # Add a refund to ensure that is factored i
        TransactionFactory(
            pay_object=transfered_from_bookings[2],
            value=-50,
            app_fee=-10,
            provider_fee=-2,
            status=Transaction.Status.COMPLETED,
            type=Transaction.Type.REFUND,
        )

        assert booking.transfered_from_chain == transfered_from_bookings

        reduction_value = booking.transfer_reduction
        assert reduction_value == 200  # 100 + 150 - 50


@pytest.mark.django_db
def test_create_transfer():
    # Create two performances for the same production
    performance_1 = PerformanceFactory(
        end=datetime.datetime.now(tz=pytz.UTC) + datetime.timedelta(days=1)
    )
    performance_2 = PerformanceFactory(
        end=datetime.datetime.now(tz=pytz.UTC) + datetime.timedelta(days=1),
        production=performance_1.production,
    )

    concession_type = ConcessionTypeFactory()

    discount = DiscountFactory()
    discount.performances.set([performance_1, performance_2])
    DiscountRequirementFactory(concession_type=concession_type, discount=discount)

    # Create a seat group which is in both performances
    seat_group_shared = SeatGroupFactory()
    PerformanceSeatingFactory(performance=performance_1, seat_group=seat_group_shared)
    PerformanceSeatingFactory(performance=performance_2, seat_group=seat_group_shared)

    # Create a seat group with no capacity in the second performance
    seat_group_shared_no_capacity = SeatGroupFactory()
    PerformanceSeatingFactory(
        performance=performance_1, seat_group=seat_group_shared_no_capacity
    )
    PerformanceSeatingFactory(
        performance=performance_2, seat_group=seat_group_shared_no_capacity, capacity=0
    )

    # Create a seat group which is only in the first performance
    seat_group = SeatGroupFactory()
    PerformanceSeatingFactory(performance=performance_1, seat_group=seat_group)

    # Create a booking for the first performance
    booking = BookingFactory(performance=performance_1, status=Booking.Status.PAID)
    # Add a ticket to the booking for each seat group
    TicketFactory(
        booking=booking, seat_group=seat_group, concession_type=concession_type
    )
    TicketFactory(
        booking=booking, seat_group=seat_group_shared, concession_type=concession_type
    )
    TicketFactory(
        booking=booking,
        seat_group=seat_group_shared_no_capacity,
        concession_type=concession_type,
    )
    # Create ticket in unassigned concession type, which should also not be copied
    TicketFactory(
        booking=booking,
        seat_group=seat_group_shared,
    )
    assert Booking.objects.count() == 1

    # Create transfer to other performance
    booking.create_transfer(performance_2)

    # Assert the new booking is created and in progress
    assert Booking.objects.count() == 2
    new_booking = Booking.objects.last()
    assert new_booking.status == Booking.Status.IN_PROGRESS

    # Assert the only ticket which is transfered is the one in both
    # perofmrances with sufficient capacity
    assert new_booking.tickets.count() == 1
    assert new_booking.tickets.first().seat_group == seat_group_shared


@pytest.mark.django_db
@pytest.mark.parametrize(
    "booking_ticket_count, capacity_remaining, is_bookable, same_performance, same_production, exception",
    [
        # Success cases
        (2, 3, True, False, True, None),
        (2, 2, True, False, True, None),
        # Doesnt raise for insufficient capacity
        (3, 2, True, False, True, None),
        # Failure cases
        (3, 2, False, False, True, NotBookableException),
        (2, 3, True, True, True, BookingTransferPerformanceUnchangedException),
        (2, 3, True, False, False, BookingTransferToDifferentProductionException),
    ],
)
def test_check_transfer_performance(  # pylint: disable=too-many-arguments
    booking_ticket_count,
    capacity_remaining,
    is_bookable,
    same_performance,
    same_production,
    exception,
):
    # Create a booking with 3 tickets
    booking = BookingFactory()
    [TicketFactory(booking=booking) for _ in range(booking_ticket_count)]

    if same_performance:
        performance = booking.performance
    elif same_production:
        performance = PerformanceFactory(production=booking.performance.production)
    else:
        performance = PerformanceFactory()

    with patch(
        "uobtheatre.productions.models.Performance.capacity_remaining",
        new_callable=PropertyMock(return_value=capacity_remaining),
    ), patch(
        "uobtheatre.productions.models.Performance.is_bookable",
        new_callable=PropertyMock(return_value=is_bookable),
    ):
        if exception:
            with pytest.raises(exception):
                booking.create_transfer(performance)
        else:
            booking.create_transfer(performance)
