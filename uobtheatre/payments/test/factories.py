import factory

from uobtheatre.bookings.test.factories import PaidBookingFactory
from uobtheatre.payments.models import Payment


class PaymentFactory(factory.django.DjangoModelFactory):

    pay_object = factory.SubFactory(PaidBookingFactory)
    type = Payment.PaymentType.PURCHASE
    provider = Payment.PaymentProvider.SQUARE_ONLINE
    value = factory.Faker("pyint", min_value=0)
    currency = "GBP"
    card_brand = "MASTERCARD"
    last_4 = "1111"

    class Meta:
        model = Payment
