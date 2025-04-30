from unittest.mock import MagicMock

import factory
from square.core.api_error import ApiError

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments import transaction_providers
from uobtheatre.payments.models import Transaction


class TransactionFactory(factory.django.DjangoModelFactory):
    pay_object = factory.SubFactory(BookingFactory)
    type = Transaction.Type.PAYMENT
    provider_name = transaction_providers.SquareOnline.name
    value = factory.Faker("pyint", min_value=100)
    currency = "GBP"
    card_brand = "MASTERCARD"
    last_4 = "1111"
    provider_transaction_id = factory.Faker(
        "bothify",
        text="##??",
    )
    provider_fee = factory.Faker("pyint", min_value=0, max_value=10)
    app_fee = factory.Faker("pyint", min_value=15, max_value=80)

    class Meta:
        model = Transaction


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
