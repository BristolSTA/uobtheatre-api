import uuid

import factory

from uobtheatre.bookings.models import (
    Booking,
    ConsessionType,
    Discount,
    DiscountRequirement,
    PerformanceSeating,
    SeatBooking,
)
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


class DiscountFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence")
    discount = 0.2

    class Meta:
        model = Discount


class ConsessionTypeFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence")

    class Meta:
        model = ConsessionType


class DiscountRequirementFactory(factory.django.DjangoModelFactory):

    number = 1
    consession_type = factory.SubFactory(ConsessionTypeFactory)

    class Meta:
        model = DiscountRequirement


class BookingFactory(factory.django.DjangoModelFactory):

    booking_reference = uuid.uuid4()
    user = factory.SubFactory(UserFactory)
    performance = factory.SubFactory(PerformanceFactory)

    class Meta:
        model = Booking


class SeatBookingFactory(factory.django.DjangoModelFactory):

    seat_group = factory.SubFactory(SeatGroupFactory)
    booking = factory.SubFactory(BookingFactory)
    consession_type = factory.SubFactory(ConsessionTypeFactory)

    class Meta:
        model = SeatBooking


class PerformanceSeatPriceFactory(factory.django.DjangoModelFactory):

    price = factory.Faker("pyint")
    performance = factory.SubFactory(PerformanceFactory)

    class Meta:
        model = PerformanceSeating
