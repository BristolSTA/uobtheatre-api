from unittest.mock import PropertyMock, patch

import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import (
    Card,
    Cash,
    PaymentMethod,
    SquareOnline,
    SquarePaymentMethodMixin,
    SquarePOS,
)
from uobtheatre.payments.square_webhooks import SquareWebhooks
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
    SquareOnline.create_payment_object(booking, 10, 5, currency="ABC")

    assert Payment.objects.count() == 1
    payment = Payment.objects.first()
    assert payment.provider == SquareOnline.name
    assert payment.type == Payment.PaymentType.PURCHASE
    assert payment.pay_object == booking
    assert payment.value == 10
    assert payment.currency == "ABC"
    assert payment.app_fee == 5


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
            payment_method.pay(100, 0, BookingFactory())

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
        payment = payment_method.pay(20, 10, booking)

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
    assert payment.app_fee == 10

    assert payment.provider_fee is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payment_method, value, expected_method_str",
    [(Cash(), 10, "CASH"), (Card(), 0, "CARD")],
)
def test_manual_pay(payment_method, value, expected_method_str):
    booking = BookingFactory()
    payment = payment_method.pay(value, 12, booking)

    assert Payment.objects.count() == 1
    assert Payment.objects.first() == payment

    assert payment.pay_object == booking
    assert payment.value == value
    assert payment.currency == "GBP"
    assert payment.provider == expected_method_str
    assert payment.type == Payment.PaymentType.PURCHASE
    assert payment.app_fee == 12


@pytest.mark.django_db
def test_square_pos_pay_success(mock_square):
    with mock_square(
        SquarePOS.client.terminal,
        "create_terminal_checkout",
        status_code=200,
        success=True,
    ):
        payment_method = SquarePOS("device_id")
        payment_method.pay(100, 14, BookingFactory())

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
            payment_method.pay(100, 0, BookingFactory())

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


@pytest.mark.django_db
def test_square_get_payments_error(mock_square):
    with mock_square(
        SquareOnline.client.payments,
        "get_payment",
        status_code=400,
        success=False,
    ):
        with pytest.raises(SquareException):
            SquareOnline.get_payment("abc")


@pytest.mark.django_db
def test_square_get_payment(mock_square):
    with mock_square(
        SquareOnline.client.payments,
        "get_payment",
        status_code=200,
        success=True,
        body={"payment": {"abc": "def"}},
    ):
        assert SquareOnline.get_payment("abc") == {"abc": "def"}


@pytest.mark.parametrize(
    "body, signature, signature_key, webhook_url, valid",
    [
        (
            {
                "merchant_id": "ML8M1AQ1GQG2K",
                "type": "terminal.checkout.updated",
                "event_id": "d395e3d0-1c5c-4372-bdf2-6955b8f44166",
                "created_at": "2021-08-13T13:45:52.789468835Z",
                "data": {
                    "type": "checkout.event",
                    "id": "dhgENdnFOPXqO",
                    "object": {
                        "checkout": {
                            "amount_money": {"amount": 111, "currency": "USD"},
                            "app_id": "sq0idp-734Md5EcFjFmwpaR0Snm6g",
                            "created_at": "2020-04-10T14:43:55.262Z",
                            "deadline_duration": "PT5M",
                            "device_options": {
                                "device_id": "907CS13101300122",
                                "skip_receipt_screen": False,
                                "tip_settings": {"allow_tipping": False},
                            },
                            "id": "dhgENdnFOPXqO",
                            "note": "A simple note",
                            "payment_ids": ["dgzrZTeIeVuOGwYgekoTHsPouaB"],
                            "reference_id": "id72709",
                            "status": "COMPLETED",
                            "updated_at": "2020-04-10T14:44:06.039Z",
                        }
                    },
                },
            },
            "xoa9/2fAXamuULrlhV1HP7C4ai4=",
            "Hd_mmQkhER3EPkpRpNQh9Q",
            "https://webhook.site/5bca8c49-e6f0-40ed-9415-4035bc05b48d",
            True,
        ),
        (
            {
                "merchant_id": "ML8M1AQ1GQG2K",
                "type": "terminal.checkout.updated",
                "event_id": "d395e3d0-1c5c-4372-bdf2-6955b8f44166",
                "created_at": "2021-08-13T13:45:52.789468835Z",
                "data": {
                    "type": "checkout.event",
                    "id": "dhgENdnFOPXqO",
                    "object": {
                        "checkout": {
                            "amount_money": {"amount": 111, "currency": "USD"},
                            "app_id": "sq0idp-734Md5EcFjFmwpaR0Snm6g",
                            "created_at": "2020-04-10T14:43:55.262Z",
                            "deadline_duration": "PT5M",
                            "device_options": {
                                "device_id": "907CS13101300122",
                                "skip_receipt_screen": False,
                                "tip_settings": {"allow_tipping": False},
                            },
                            "id": "dhgENdnFOPXqO",
                            "note": "A simple note",
                            "payment_ids": ["dgzrZTeIeVuOGwYgekoTHsPouaB"],
                            "reference_id": "id72709",
                            "status": "NOTCOMPLETED",
                            "updated_at": "2020-04-10T14:44:06.039Z",
                        }
                    },
                },
            },
            "xoa9/2fAXamuULrlhV1HP7C4ai4=",
            "Hd_mmQkhER3EPkpRpNQh9Q",
            "https://webhook.site/5bca8c49-e6f0-40ed-9415-4035bc05b48d",
            False,
        ),
    ],
)
def test_is_valid_callback(body, signature, signature_key, webhook_url, valid):
    with patch.object(
        SquareWebhooks, "webhook_signature_key", new_callable=PropertyMock
    ) as key_mock, patch.object(
        SquareWebhooks, "webhook_url", new_callable=PropertyMock
    ) as url_mock:
        key_mock.return_value = signature_key
        url_mock.return_value = webhook_url
        assert SquareWebhooks.is_valid_callback(body, signature) == valid


@pytest.mark.django_db
def test_handle_terminal_checkout_updated_webhook_completed(mock_square):
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    data = {
        "object": {
            "checkout": {
                "amount_money": {"amount": 111, "currency": "USD"},
                "reference_id": booking.payment_reference_id,
                "payment_ids": ["dgzrZTeIeVuOGwYgekoTHsPouaB"],
                "status": "COMPLETED",
            }
        },
    }

    with mock_square(
        SquarePaymentMethodMixin.client.payments,
        "get_payment",
        status_code=200,
        success=True,
        body={
            "payment": {
                "status": "COMPLETED",
            }
        },
    ) as mock:
        SquarePOS.handle_terminal_checkout_updated_webhook(data)

    mock.assert_called_once_with("dgzrZTeIeVuOGwYgekoTHsPouaB")
    booking.refresh_from_db()
    assert booking.status == Booking.BookingStatus.PAID
    assert Payment.objects.count() == 1

    payment = Payment.objects.first()
    payment.provider_payment_id = "dgzrZTeIeVuOGwYgekoTHsPouaB"
    payment.value = 111
    payment.currency = "USD"


@pytest.mark.django_db
def test_handle_terminal_checkout_updated_webhook_completed_no_completed_payments(
    mock_square,
):
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    data = {
        "object": {
            "checkout": {
                "amount_money": {"amount": 111, "currency": "USD"},
                "reference_id": booking.payment_reference_id,
                "payment_ids": [
                    "dgzrZTeIeVuOGwYgekoTHsPouaB",
                    "dgzrZTeIeVuOGwYgekoTHsPouaC",
                ],
                "status": "COMPLETED",
            }
        },
    }

    # Mock get_payment to return all payments as pending
    with mock_square(
        SquarePaymentMethodMixin.client.payments,
        "get_payment",
        status_code=200,
        success=True,
        body={
            "payment": {
                "status": "PENDING",
            }
        },
    ):
        SquarePOS.handle_terminal_checkout_updated_webhook(data)
        booking.refresh_from_db()
        assert booking.status == Booking.BookingStatus.IN_PROGRESS
        assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_square_pos_handle_terminal_checkout_updated_webhook_not_completed():
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    data = {
        "object": {
            "checkout": {
                "amount_money": {"amount": 111, "currency": "USD"},
                "reference_id": booking.payment_reference_id,
                "payment_ids": ["dgzrZTeIeVuOGwYgekoTHsPouaB"],
                "status": "FAILED",
            }
        },
    }
    SquarePOS.handle_terminal_checkout_updated_webhook(data)
    booking.refresh_from_db()
    assert booking.status == Booking.BookingStatus.IN_PROGRESS
    assert Payment.objects.count() == 0


def test_square_pos_handle_webhook_terminal_checkout_updated():
    with patch.object(SquarePOS, "handle_terminal_checkout_updated_webhook") as mock:
        SquarePOS.handle_webhook(
            {
                "type": "terminal.checkout.updated",
                "data": {
                    "type": "checkout.event",
                    "extra": "data",
                },
            },
        )

    mock.assert_called_once_with(
        {
            "type": "checkout.event",
            "extra": "data",
        }
    )


def test_square_pos_handle_webhook_other_type():
    with patch.object(SquarePOS, "handle_terminal_checkout_updated_webhook") as mock:
        SquarePOS.handle_webhook({"type": "other"})

    mock.assert_not_called()
