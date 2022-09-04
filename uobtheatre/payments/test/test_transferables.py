# pylint: disable=too-many-lines
from unittest.mock import PropertyMock, patch

import pytest

from uobtheatre.bookings.exceptions import (
    BookingTransferPerformanceUnchangedException,
    BookingTransferToDifferentProductionException,
)
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
from uobtheatre.payments.transferables import Transferable
from uobtheatre.productions.exceptions import (
    NotBookableException,
    NotEnoughCapacityException,
)


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
def test_transferred_to():
    booking_3 = BookingFactory()
    booking_2 = BookingFactory(transfered_from=booking_3)
    booking_1 = BookingFactory(transfered_from=booking_2)

    booking_4 = BookingFactory()

    assert booking_1.transferred_to is None
    assert booking_4.transferred_to is None
    assert booking_2.transferred_to == booking_1
    assert booking_3.transferred_to == booking_2


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


def test_transferable_total():
    # pylint: disable=missing-class-docstring
    class MockTransferable(Transferable):
        display_name = "MockTransferable"
        subtotal = 50
        transfer_reduction = 20
        misc_costs_value = 10
        misc_cost_types = []
        payment_reference_id = None

    transferable = MockTransferable()
    assert transferable.total == 40
