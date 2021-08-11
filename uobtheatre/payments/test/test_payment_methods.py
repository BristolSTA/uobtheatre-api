import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import (
    Card,
    Cash,
    SquareOnline,
    SquarePOS,
    payment_method_is,
)
from uobtheatre.utils.exceptions import SquareException


@pytest.mark.parametrize(
    "payment_method_name, payment_method_class, expect_eq",
    [
        ("SQUAREONLINE", SquareOnline, True),
        ("squareonline", SquareOnline, True),
        ("SquareOnline", SquareOnline, True),
        ("notsqsuareonline", SquareOnline, False),
        ("SQUAREONLINE", Cash, False),
        ("CASH", Cash, True),
        ("CARD", Card, True),
        ("SQUAREPOS", SquarePOS, True),
    ],
)
def test_payment_method_is(payment_method_name, payment_method_class, expect_eq):
    assert payment_method_is(payment_method_name, payment_method_class) == expect_eq


@pytest.mark.django_db
def test_square_online_pay_failure(mock_square):
    """
    Test paying a booking with square
    """
    with mock_square(
        SquareOnline.client.payments,
        "create_payment",
        reason_phrase="Some phrase",
        status_code=400,
        success=False,
    ):
        payment_method = SquareOnline("nonce", "abc")
        with pytest.raises(SquareException):
            payment_method.pay(100, BookingFactory())

    # Assert no payments are created
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_booking_pay_success(mock_square):
    """
    Test paying a booking with square
    """
    with mock_square(
        SquareOnline.client.payments,
        "create_payment",
        body={
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
                    "amount": 10,
                },
            }
        },
        success=True,
    ):
        booking = BookingFactory()
        payment_method = SquareOnline("nonce", "key")
        payment = payment_method.pay(20, booking)

    # Assert a payment of the correct type is created
    assert payment is not None
    assert payment.pay_object == booking
    assert payment.value == 10
    assert payment.currency == "GBP"
    assert payment.card_brand == "MASTERCARD"
    assert payment.last_4 == "1234"
    assert payment.provider_payment_id == "abc"
    assert payment_method_is(payment.provider, SquareOnline)
    assert payment.type == Payment.PaymentType.PURCHASE
