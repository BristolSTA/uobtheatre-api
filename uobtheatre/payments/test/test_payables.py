from unittest.mock import PropertyMock, patch

import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payment_methods import Card, Cash, SquareOnline
from uobtheatre.payments.test.factories import PaymentFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_payable_provider_payment_value():
    booking = BookingFactory()

    PaymentFactory(pay_object=booking, provider_fee=20)
    PaymentFactory(pay_object=booking, provider_fee=10)

    assert booking.provider_payment_value == 30


@pytest.mark.django_db
def test_payable_app_payment_value():
    booking = BookingFactory()

    PaymentFactory(pay_object=booking, provider_fee=20, app_fee=100)
    PaymentFactory(pay_object=booking, provider_fee=10, app_fee=150)

    assert booking.app_payment_value == 220


@pytest.mark.django_db
def test_payable_society_payment_value():
    booking = BookingFactory()

    PaymentFactory(pay_object=booking, app_fee=100, value=200)
    PaymentFactory(pay_object=booking, app_fee=150, value=400)

    assert booking.society_revenue == 350


@pytest.mark.django_db
def test_payable_total_sales():
    booking = BookingFactory()

    PaymentFactory(pay_object=booking, app_fee=100, value=200)
    PaymentFactory(pay_object=booking, app_fee=150, value=400)

    assert booking.total_sales == 600


@pytest.mark.django_db
def test_society_transfer_value():
    booking = BookingFactory()

    PaymentFactory(pay_object=booking, app_fee=100, value=200, provider=Cash.name)
    PaymentFactory(pay_object=booking, app_fee=200, value=600, provider=Card.name)
    PaymentFactory(
        pay_object=booking, app_fee=150, value=400, provider=SquareOnline.name
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
    [PaymentFactory(status=Transaction.PaymentStatus.COMPLETED) for _ in range(10)]

    pay_object = BookingFactory()
    [
        PaymentFactory(
            value=value, type=Transaction.PaymentType.PURCHASE, pay_object=pay_object
        )
        for value in payment_values
    ]

    if has_pending:
        PaymentFactory(pay_object=pay_object, status=Transaction.PaymentStatus.PENDING)

    assert pay_object.is_refunded == is_refunded

    if payment := pay_object.transactions.first():
        assert payment.is_refunded == is_refunded


@pytest.mark.django_db
@pytest.mark.parametrize(
    "can_be_refunded,send_email", [(True, False), (False, True), (True, True)]
)
def test_payable_refund(mailoutbox, can_be_refunded, send_email):
    pay_object = BookingFactory()
    payment_1 = PaymentFactory(pay_object=pay_object)
    payment_2 = PaymentFactory(pay_object=pay_object)
    PaymentFactory()  # Payment not associated with booking

    with patch.object(
        Booking,
        "can_be_refunded",
        new_callable=PropertyMock(return_value=can_be_refunded),
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
