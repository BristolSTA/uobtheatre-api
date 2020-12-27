import uuid

import factory

from uobtheatre.bookings.models import (Booking, ConcessionType, Discount,
                                        DiscountRequirement, Ticket)
from uobtheatre.productions.models import PerformanceSeatGroup
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


class DiscountFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence")
    discount = 0.2

    class Meta:
        model = Discount


class ConcessionTypeFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence")

    class Meta:
        model = ConcessionType


class DiscountRequirementFactory(factory.django.DjangoModelFactory):

    number = 1
    concession_type = factory.SubFactory(ConcessionTypeFactory)

    class Meta:
        model = DiscountRequirement


class BookingFactory(factory.django.DjangoModelFactory):

    booking_reference = uuid.uuid4()
    user = factory.SubFactory(UserFactory)
    performance = factory.SubFactory(PerformanceFactory)

    class Meta:
        model = Booking


class PerformanceSeatingFactory(factory.django.DjangoModelFactory):

    price = factory.Faker("pyint")
    performance = factory.SubFactory(PerformanceFactory)
    capacity = factory.Faker("pyint")
    seat_group = factory.SubFactory(SeatGroupFactory)

    class Meta:
        model = PerformanceSeatGroup


class TicketFactory(factory.django.DjangoModelFactory):

    seat_group = factory.SubFactory(SeatGroupFactory)
    booking = factory.SubFactory(BookingFactory)
    concession_type = factory.SubFactory(ConcessionTypeFactory)

    class Meta:
        model = Ticket
