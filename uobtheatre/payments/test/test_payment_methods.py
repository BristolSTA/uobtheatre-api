import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import (
    Card,
    Cash,
    PaymentMethod,
    SquareOnline,
    SquarePOS,
)
from uobtheatre.utils.exceptions import SquareException


def test_payment_method_all():
    assert PaymentMethod.__all__ == [
        Cash,
        Card,
        SquarePOS,
        SquareOnline,
    ]


def test_payment_method_choice():
    assert PaymentMethod.choices == [  # pylint: disable=comparison-with-callable
        ("CASH", "CASH"),
        ("CARD", "CARD"),
        ("SQUARE_POS", "SQUARE_POS"),
        ("SQUARE_ONLINE", "SQUARE_ONLINE"),
    ]


@pytest.mark.parametrize(
    "payment_method, expected_name",
    [
        (SquareOnline, "SQUARE_ONLINE"),
        (SquarePOS, "SQUARE_POS"),
        (SquarePOS("123"), "SQUARE_POS"),
    ],
)
def test_payment_method_name(payment_method, expected_name):
    assert payment_method.name == expected_name


@pytest.mark.parametrize(
    "input_name, expected_output_name",
    [
        ("SquareOnline", "SQUARE_ONLINE"),
        ("ABC", "ABC"),
        ("ABCOnline", "ABC_ONLINE"),
    ],
)
def test_generate_name(input_name, expected_output_name):
    assert PaymentMethod.generate_name(input_name) == expected_output_name


@pytest.mark.django_db
def test_create_paymnet_object():
    booking = BookingFactory()
    SquareOnline.create_payment_object(booking, 10, currency="ABC")

    assert Payment.objects.count() == 1
    payment = Payment.objects.first()
    assert payment.provider == SquareOnline.name
    assert payment.type == Payment.PaymentType.PURCHASE
    assert payment.pay_object == booking
    assert payment.value == 10
    assert payment.currency == "ABC"


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
def test_square_online_pay_success(mock_square):
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

    # Assert the returned payment gets saved
    assert Payment.objects.count() == 1
    assert Payment.objects.first() == payment

    # Assert a payment of the correct type is created
    assert payment is not None
    assert payment.pay_object == booking
    assert payment.value == 10
    assert payment.currency == "GBP"
    assert payment.card_brand == "MASTERCARD"
    assert payment.last_4 == "1234"
    assert payment.provider_payment_id == "abc"
    assert payment.provider == "SQUARE_ONLINE"
    assert payment.type == Payment.PaymentType.PURCHASE


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payment_method, value, expected_method_str",
    [(Cash(), 10, "CASH"), (Card(), 0, "CARD")],
)
def test_manual_pay(payment_method, value, expected_method_str):
    booking = BookingFactory()
    payment = payment_method.pay(value, booking)

    assert Payment.objects.count() == 1
    assert Payment.objects.first() == payment

    assert payment.pay_object == booking
    assert payment.value == value
    assert payment.currency == "GBP"
    assert payment.provider == expected_method_str
    assert payment.type == Payment.PaymentType.PURCHASE


@pytest.mark.django_db
def test_square_pos_pay_success(mock_square):
    with mock_square(
        SquarePOS.client.terminal,
        "create_terminal_checkout",
        status_code=200,
        success=True,
    ):
        payment_method = SquarePOS("device_id")
        payment_method.pay(100, BookingFactory())

    # Assert no payments are created. A payment should only be created by the
    # webhook.
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_square_pos_pay_failure(mock_square):
    with mock_square(
        SquarePOS.client.terminal,
        "create_terminal_checkout",
        status_code=400,
        success=False,
        reason_phrase="Device not found",
    ):
        with pytest.raises(SquareException):
            payment_method = SquarePOS("device_id")
            payment_method.pay(100, BookingFactory())

    # Assert no payments are created
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_square_pos_list_devices_success(mock_square):
    with mock_square(
        SquarePOS.client.devices,
        "list_device_codes",
        status_code=200,
        success=True,
        body={"device_codes": ["a", "b", "c"]},
    ):
        assert SquarePOS.list_devices() == ["a", "b", "c"]


@pytest.mark.django_db
def test_square_pos_list_devices_failure(mock_square):
    with mock_square(
        SquarePOS.client.devices,
        "list_device_codes",
        status_code=400,
        success=False,
    ):
        with pytest.raises(SquareException):
            SquarePOS.list_devices()


# TODO
# @pytest.mark.square_integration
