from unittest.mock import PropertyMock, patch

import pytest
from pytest_django.asserts import assertQuerysetEqual

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.tasks import refund_payable
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import Card, Cash, SquareOnline
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.test.factories import TaskResultFactory


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
        ([], False, False),
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
    "status,num_payments,is_refunded,is_locked,error_message",
    [
        (
            Booking.Status.IN_PROGRESS,
            1,
            True,
            True,
            "Booking (ABCD123) can't be refunded due to it's status (IN_PROGRESS)",
        ),
        (
            Booking.Status.PAID,
            1,
            True,
            True,
            "Booking (ABCD123) can't be refunded because is already refunded",
        ),
        (
            Booking.Status.PAID,
            1,
            False,
            True,
            "Booking (ABCD123) can't be refunded because it is locked",
        ),
        (
            Booking.Status.PAID,
            1,
            False,
            False,
            None,
        ),
        (
            Booking.Status.PAID,
            0,
            False,
            False,
            "Booking (ABCD123) can't be refunded because it has no payments",
        ),
    ],
)
def test_validate_cant_be_refunded(
    status, num_payments, is_refunded, is_locked, error_message
):
    booking = BookingFactory(status=status, reference="ABCD123")
    [TransactionFactory(pay_object=booking) for _ in range(num_payments)]

    with patch(
        "uobtheatre.payments.payables.Payable.is_refunded",
        new_callable=PropertyMock(return_value=is_refunded),
    ), patch(
        "uobtheatre.payments.payables.Payable.is_locked",
        new_callable=PropertyMock(return_value=is_locked),
    ):
        value = booking.validate_cant_be_refunded()
        if error_message:
            assert isinstance(value, CantBeRefundedException)
            assert value.message == error_message
        else:
            assert value is None


@pytest.mark.django_db
def test_async_refund():
    booking = BookingFactory(id=45)
    with patch.object(refund_payable, "delay") as mock:
        booking.async_refund(UserFactory(id=3))
        mock.assert_called_once_with(45, booking.content_type.pk, 3)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "can_be_refunded,send_email,do_async",
    [
        (True, False, False),
        (False, True, False),
        (True, True, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    ],
)
def test_payable_refund(mailoutbox, can_be_refunded, send_email, do_async):
    pay_object = BookingFactory()
    payment_1 = TransactionFactory(pay_object=pay_object)
    payment_2 = TransactionFactory(pay_object=pay_object)
    TransactionFactory()  # Payment not associated with booking

    with patch.object(
        Payable,
        "validate_cant_be_refunded",
        return_value=(CantBeRefundedException if not can_be_refunded else None),
    ), patch(
        "uobtheatre.payments.models.Transaction.refund", autospec=True
    ) as payment_refund, patch(
        "uobtheatre.payments.models.Transaction.async_refund", autospec=True
    ) as payment_refund_async:

        def test():
            pay_object.refund(
                UserFactory(), do_async=do_async, send_admin_email=send_email
            )

        if not can_be_refunded:
            with pytest.raises(CantBeRefundedException):
                test()
        else:
            test()

        mock = payment_refund_async if do_async else payment_refund

        assert mock.call_count == (2 if can_be_refunded else 0)
        assert len(mailoutbox) == (1 if can_be_refunded and send_email else 0)
        if can_be_refunded:
            mock.assert_any_call(payment_1)
            mock.assert_any_call(payment_2)


@pytest.mark.django_db
def test_payable_associated_tasks():
    payable = BookingFactory()
    other_payable = BookingFactory()
    transaction = TransactionFactory(type=Transaction.Type.PAYMENT, pay_object=payable)

    # A related task for the payments
    related_payment_task = TaskResultFactory(
        task_name="uobtheatre.payments.tasks.refund_payment",
        task_args=f'"({transaction.id},)"',
    )

    # A related task for the booking
    related_task = TaskResultFactory(
        task_name="uobtheatre.payments.tasks.refund_payable",
        task_args=f'"({payable.id}, {payable.content_type.id}, abc)"',
    )

    # Task for different booking
    TaskResultFactory(
        task_name="uobtheatre.payments.tasks.refund_payable",
        task_args=f'"({other_payable.id}, {payable.content_type.id}, abc)"',
    )
    # Task for different contenttype
    TaskResultFactory(
        task_name="uobtheatre.payments.tasks.refund_payable",
        task_args=f'"({payable.id}, {payable.content_type.id + 1}, abc)"',
    )
    # Differnt tasks
    TaskResultFactory(
        task_name="uobtheatre.payments.tasks.refund_performance",
        task_args=f'"({payable.id}, {payable.content_type.id}, abc)"',
    )

    assertQuerysetEqual(payable.associated_tasks, [related_task, related_payment_task])


@pytest.mark.django_db
@pytest.mark.parametrize("count", [0, 4, 3])
def test_annotate_transaction_count(count):
    payable = BookingFactory()
    [
        TransactionFactory(type=Transaction.Type.PAYMENT, pay_object=payable)
        for _ in range(count)
    ]
    assertQuerysetEqual(
        payable.qs.annotate_transaction_count().values_list(
            "transaction_count", flat=True
        ),
        [count],
    )


@pytest.mark.django_db
def test_annotate_transaction_value():
    payable = BookingFactory()
    assertQuerysetEqual(
        payable.qs.annotate_transaction_value().values_list(
            "transaction_totals", flat=True
        ),
        [0],
    )

    TransactionFactory(value=10, pay_object=payable)
    TransactionFactory(value=-20, pay_object=payable)
    TransactionFactory(value=50, pay_object=payable)

    assertQuerysetEqual(
        payable.qs.annotate_transaction_value().values_list(
            "transaction_totals", flat=True
        ),
        [40],
    )


@pytest.mark.django_db
def test_queryset_refunded():
    # Refunded payable - Refunded
    payable1 = BookingFactory()
    TransactionFactory(value=2, pay_object=payable1)
    TransactionFactory(value=8, pay_object=payable1)
    TransactionFactory(value=-10, pay_object=payable1)

    # Payable with no payments - Not refunded
    payable2 = BookingFactory()

    # Payable with single payment - Not refunded
    payable3 = BookingFactory()
    TransactionFactory(value=2, pay_object=payable3)

    # Payable with single payment - Not refunded
    payable4 = BookingFactory()
    TransactionFactory(value=2, pay_object=payable4)
    TransactionFactory(value=-3, pay_object=payable4)

    assertQuerysetEqual(
        Booking.objects.refunded(),
        [payable1],
    )

    assertQuerysetEqual(
        Booking.objects.refunded(bool_val=False),
        [payable2, payable3, payable4],
        ordered=False,
    )
