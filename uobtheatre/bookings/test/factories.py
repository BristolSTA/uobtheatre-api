import uuid

import factory

from uobtheatre.bookings.models import Booking, ConsessionType, Discount
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory


class DiscountFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence")
    discount = 0.2

    class Meta:
        model = Discount


class ConsessionTypeFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence")

    class Meta:
        model = ConsessionType


class BookingFactory(factory.django.DjangoModelFactory):

    booking_reference = uuid.uuid4()
    user = factory.SubFactory(UserFactory)
    performance = factory.SubFactory(PerformanceFactory)

    class Meta:
        model = Booking
