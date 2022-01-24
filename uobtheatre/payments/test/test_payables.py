from unittest.mock import patch

import pytest
from pytest_django.asserts import assertQuerysetEqual

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import Card, Cash, SquareOnline
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_payable_query_set():
    booking_1 = BookingFactory()  # Booking with pending payments - locked
    TransactionFactory(pay_object=booking_1, status=Transaction.Status.PENDING)
    TransactionFactory(pay_object=booking_1, status=Transaction.Status.COMPLETED)

    booking_2 = (
        BookingFactory()
    )  # Booking with a transaciton value sum of zero - refunded
    TransactionFactory(
        pay_object=booking_2, status=Transaction.Status.COMPLETED, value=200
    )
    TransactionFactory(
        pay_object=booking_2,
        status=Transaction.Status.COMPLETED,
        value=-200,
        type=Transaction.Type.REFUND,
    )

    booking_3 = BookingFactory()  # A completed and paid for booking. Shouldn't show up
    TransactionFactory(pay_object=booking_3, status=Transaction.Status.COMPLETED)

    assertQuerysetEqual(Booking.objects.locked(), [booking_1])
    assertQuerysetEqual(Booking.objects.refunded(), [booking_2])


@pytest.mark.django_db
def test_payable_provider_payment_value():
    booking = BookingFactory()

    TransactionFactory(pay_object=booking, provider_fee=20)
    TransactionFactory(pay_object=booking, provider_fee=10)

    assert booking.provider_payment_value == 30


@pytest.mark.django_db
def test_payable_app_payment_value():
    booking = BookingFactory()

    TransactionFactory(pay_object=booking, provider_fee=20, app_fee=100)
    TransactionFactory(pay_object=booking, provider_fee=10, app_fee=150)

    assert booking.app_payment_value == 220


@pytest.mark.django_db
def test_payable_society_payment_value():
    booking = BookingFactory()

    TransactionFactory(pay_object=booking, app_fee=100, value=200)
    TransactionFactory(pay_object=booking, app_fee=150, value=400)

    assert booking.society_revenue == 350


@pytest.mark.django_db
def test_payable_total_sales():
    booking = BookingFactory()

    TransactionFactory(pay_object=booking, app_fee=100, value=200)
    TransactionFactory(pay_object=booking, app_fee=150, value=400)

    assert booking.total_sales == 600


@pytest.mark.django_db
def test_society_transfer_value():
    booking = BookingFactory()

    TransactionFactory(
        pay_object=booking, app_fee=100, value=200, provider_name=Cash.name
    )
    TransactionFactory(
        pay_object=booking, app_fee=200, value=600, provider_name=Card.name
    )
    TransactionFactory(
        pay_object=booking, app_fee=150, value=400, provider_name=SquareOnline.name
    )

    assert booking.society_transfer_value == 550


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payment_values, has_pending, is_refunded",
    [
        ([10, -10], False, True),
        ([1, 11, 12, -10], False, False),
        ([5, 5, -10], False, True),
        ([], False, True),
        ([-10], False, False),
        ([10], False, False),
        ([5, -5], True, False),
    ],
)
def test_is_refunded(payment_values, has_pending, is_refunded):
    # Create some payments for different payobjects
    [TransactionFactory(status=Transaction.Status.COMPLETED) for _ in range(10)]

    pay_object = BookingFactory()
    [
        TransactionFactory(
            value=value, type=Transaction.Type.PAYMENT, pay_object=pay_object
        )
        for value in payment_values
    ]

    if has_pending:
        TransactionFactory(pay_object=pay_object, status=Transaction.Status.PENDING)

    assert pay_object.is_refunded == is_refunded

    if payment := pay_object.transactions.first():
        assert payment.is_refunded == is_refunded


@pytest.mark.django_db
@pytest.mark.parametrize(
    "has_pending_transaction",
    [False, True],
)
def test_is_locked(has_pending_transaction):
    booking = BookingFactory()
    TransactionFactory(
        pay_object=booking,
        status=Transaction.Status.PENDING
        if has_pending_transaction
        else Transaction.Status.COMPLETED,
    )

    assert booking.is_locked == has_pending_transaction


@pytest.mark.django_db
@pytest.mark.parametrize(
    "can_be_refunded,send_email", [(True, False), (False, True), (True, True)]
)
def test_payable_refund(mailoutbox, can_be_refunded, send_email):
    pay_object = BookingFactory()
    payment_1 = TransactionFactory(pay_object=pay_object)
    payment_2 = TransactionFactory(pay_object=pay_object)
    TransactionFactory()  # Payment not associated with booking

    with patch.object(
        Booking,
        "validate_cant_be_refunded",
        side_effect=(CantBeRefundedException if not can_be_refunded else None),
        return_value=None,
    ), patch(
        "uobtheatre.payments.models.Transaction.refund", autospec=True
    ) as payment_refund:

        def test():
            pay_object.refund(UserFactory(), send_admin_email=send_email)

        if not can_be_refunded:
            with pytest.raises(CantBeRefundedException):
                test()
        else:
            test()

        assert payment_refund.call_count == (2 if can_be_refunded else 0)
        assert len(mailoutbox) == (1 if can_be_refunded and send_email else 0)
        if can_be_refunded:
            payment_refund.assert_any_call(payment_1)
            payment_refund.assert_any_call(payment_2)
