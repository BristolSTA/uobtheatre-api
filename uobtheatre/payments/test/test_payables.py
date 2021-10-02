import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.payment_methods import Card, Cash, SquareOnline
from uobtheatre.payments.test.factories import PaymentFactory


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
def test_society_transfer_value():
    booking = BookingFactory()

    PaymentFactory(pay_object=booking, app_fee=100, value=200, provider=Cash.name)
    PaymentFactory(pay_object=booking, app_fee=200, value=600, provider=Card.name)
    PaymentFactory(
        pay_object=booking, app_fee=150, value=400, provider=SquareOnline.name
    )

    assert booking.society_transfer_value == 550
