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
from uobtheatre.payments.test.factories import PaymentFactory
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
        (SquarePOS("123", "ikey"), "SQUARE_POS"),
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
    assert payment.status == Payment.PaymentStatus.COMPLETED
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
        body={
            "checkout": {
                "id": "ScegTcoaJ0kqO",
                "amount_money": {"amount": 100, "currency": "GBP"},
                "device_options": {
                    "device_id": "121CS145A5000029",
                },
                "status": "PENDING",
            }
        },
    ):
        payment_method = SquarePOS("device_id", "ikey")
        payment_method.pay(100, 14, BookingFactory())

    # Assert a payment is created that links to the checkout.
    assert Payment.objects.count() == 1

    payment = Payment.objects.first()
    assert payment.value == 100
    assert payment.status == Payment.PaymentStatus.PENDING
    assert payment.app_fee == 14
    assert payment.provider_fee is None
    assert payment.provider_payment_id == "ScegTcoaJ0kqO"


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
            payment_method = SquarePOS("device_id", "ikey")
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
def test_handle_terminal_checkout_updated_webhook_completed():
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    payment = PaymentFactory()
    data = {
        "object": {
            "checkout": {
                "id": payment.provider_payment_id,
                "amount_money": {"amount": 111, "currency": "USD"},
                "reference_id": booking.payment_reference_id,
                "payment_ids": ["dgzrZTeIeVuOGwYgekoTHsPouaB"],
                "status": "COMPLETED",
            }
        },
    }

    SquarePOS.handle_terminal_checkout_updated_webhook(data)
    booking.refresh_from_db()

    assert booking.status == Booking.BookingStatus.PAID
    assert Payment.objects.count() == 1

    payment = Payment.objects.first()
    assert payment.status == Payment.PaymentStatus.COMPLETED


@pytest.mark.django_db
def test_handle_terminal_checkout_updated_webhook_not_completed():
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    data = {
        "object": {
            "checkout": {
                "reference_id": booking.payment_reference_id,
                "status": "NOTCOMPLETED",
            }
        },
    }

    SquarePOS.handle_terminal_checkout_updated_webhook(data)

    booking.refresh_from_db()
    assert booking.status == Booking.BookingStatus.IN_PROGRESS


@pytest.mark.django_db
def test_handle_terminal_checkout_updated_canceled():
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    payment = PaymentFactory(provider_payment_id="abc", provider=SquarePOS.name)
    data = {
        "object": {
            "checkout": {
                "id": "abc",
                "reference_id": booking.payment_reference_id,
                "status": "CANCELED",
            }
        },
    }

    SquarePOS.handle_terminal_checkout_updated_webhook(data)

    booking.refresh_from_db()
    assert booking.status == Booking.BookingStatus.IN_PROGRESS
    assert not Payment.objects.filter(id=payment.id).exists()


@pytest.mark.django_db
def test_handle_terminal_checkout_updated_canceled_no_payments():
    """
    When square sends a webhook that cancels a checkout. If there is no
    associated payment then do nothing.
    """
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    data = {
        "object": {
            "checkout": {
                "id": "abc",
                "reference_id": booking.payment_reference_id,
                "status": "CANCELED",
            }
        },
    }

    SquarePOS.handle_terminal_checkout_updated_webhook(data)

    booking.refresh_from_db()
    assert booking.status == Booking.BookingStatus.IN_PROGRESS


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
def test_square_get_checkout_error(mock_square):
    with mock_square(
        SquarePOS.client.terminal,
        "get_terminal_checkout",
        status_code=400,
        success=False,
    ):
        with pytest.raises(SquareException):
            SquarePOS.get_checkout("abc")


@pytest.mark.django_db
def test_square_get_checkout(mock_square):
    with mock_square(
        SquarePOS.client.terminal,
        "get_terminal_checkout",
        status_code=200,
        success=True,
        body={"checkout": {"abc": "def"}},
    ):
        assert SquarePOS.get_checkout("abc") == {"abc": "def"}


@pytest.mark.django_db
def test_square_pos_cancel_failure(mock_square):
    payment = PaymentFactory()
    with mock_square(
        SquarePOS.client.terminal,
        "cancel_terminal_checkout",
        status_code=400,
        success=False,
        reason_phrase="Checkout not found",
    ):
        with pytest.raises(SquareException):
            payment_method = SquarePOS("device_id", "ikey")
            payment_method.cancel(payment)

    # Assert payment not deleted
    assert Payment.objects.filter(id=payment.id).exists()
