import factory

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments import payment_methods
from uobtheatre.payments.models import Payment


class PaymentFactory(factory.django.DjangoModelFactory):

    pay_object = factory.SubFactory(BookingFactory)
    type = Payment.PaymentType.PURCHASE
    provider = payment_methods.SquareOnline.__name__
    value = factory.Faker("pyint", min_value=0)
    currency = "GBP"
    card_brand = "MASTERCARD"
    last_4 = "1111"

    class Meta:
        model = Payment
