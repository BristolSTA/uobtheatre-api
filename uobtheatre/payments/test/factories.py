from unittest.mock import MagicMock

import factory

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments import payment_methods
from uobtheatre.payments.models import Payment


class PaymentFactory(factory.django.DjangoModelFactory):

    pay_object = factory.SubFactory(BookingFactory)
    type = Payment.PaymentType.PURCHASE
    provider = payment_methods.SquareOnline.name
    value = factory.Faker("pyint", min_value=0)
    currency = "GBP"
    card_brand = "MASTERCARD"
    last_4 = "1111"
    provider_payment_id = factory.Faker(
        "bothify",
        text="##??",
    )

    class Meta:
        model = Payment


class MockApiResponse:
    """
    Mock of the Square API response class.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        reason_phrase="Some phrase",
        status_code=400,
        success=False,
        body=None,
        errors=None,
    ):
        """Initialse the mock api response"""
        self.reason_phrase = reason_phrase
        self.status_code = status_code
        self.success = success
        self.body = body
        self.errors = errors

    def is_success(self):
        return self.success


def mock_payment_method(is_refundable: bool = True, refund_method=None):
    """
    Mock of the payment method class.
    """

    class MockPaymentMethod:  # pylint: disable=missing-class-docstring
        pay = MagicMock(return_value=Payment())

        @classmethod
        @property
        def refund_method(cls):
            return refund_method

        @classmethod
        @property
        def is_refundable(cls):
            return is_refundable

    return MockPaymentMethod()


def mock_refund_method():
    class MockRefundMethod:  # pylint: disable=no-method-argument
        refund = MagicMock(return_value=None)

    return MockRefundMethod()
