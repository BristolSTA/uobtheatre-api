from unittest.mock import MagicMock

import factory

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments import transaction_providers
from uobtheatre.payments.models import Transaction


class TransactionFactory(factory.django.DjangoModelFactory):
    pay_object = factory.SubFactory(BookingFactory)
    type = Transaction.Type.PAYMENT
    provider_name = transaction_providers.SquareOnline.name
    value = factory.Faker("pyint", min_value=0)
    currency = "GBP"
    card_brand = "MASTERCARD"
    last_4 = "1111"
    provider_transaction_id = factory.Faker(
        "bothify",
        text="##??",
    )

    class Meta:
        model = Transaction


class MockApiResponse:
    """
    Mock of the Square API response class.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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


def mock_payment_method(
    name="payment_method",
    is_refundable: bool = True,
    automatic_refund_provider=None,
):
    """
    Mock of the payment method class.
    """

    class MockPaymentMethod:  # pylint: disable=missing-class-docstring
        pay = MagicMock(return_value=TransactionFactory())

        @property
        def name(self):
            return name

        @property
        def automatic_refund_provider(self):
            return automatic_refund_provider

        @property
        def is_refundable(self):
            return is_refundable

    return MockPaymentMethod()


def mock_refund_method(name="refund_method"):
    """
    Mock of refund provider
    """

    class MockRefundMethod:  # pylint: disable=no-method-argument,missing-class-docstring
        refund = MagicMock(return_value=None)

        @classmethod
        @property
        def name(cls):
            return name

    return MockRefundMethod()
