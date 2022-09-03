import factory

from uobtheatre.bookings.models import Booking, MiscCost, Ticket
from uobtheatre.discounts.models import DiscountRequirement
from uobtheatre.discounts.test.factories import DiscountFactory
from uobtheatre.payments.payables import Payable
from uobtheatre.productions.models import PerformanceSeatGroup
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


class PercentageMiscCostFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence")
    description = factory.Faker("sentence")
    percentage = factory.Faker("pyfloat", min_value=0, max_value=1)
    type = MiscCost.Type.BOOKING

    class Meta:
        model = MiscCost


class ValueMiscCostFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence")
    description = factory.Faker("sentence")
    value = factory.Faker("pyint")
    type = MiscCost.Type.BOOKING

    class Meta:
        model = MiscCost


class BookingFactory(factory.django.DjangoModelFactory):

    user = factory.SubFactory(UserFactory)
    creator = factory.SubFactory(UserFactory)
    performance = factory.SubFactory(PerformanceFactory)
    status = Payable.Status.PAID

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
    concession_type = factory.SubFactory(
        "uobtheatre.discounts.test.factories.ConcessionTypeFactory"
    )

    class Meta:
        model = Ticket


def add_ticket_to_booking(booking, checked_in=False):
    """Adds a ticket of price 100 to the booking"""
    ticket = TicketFactory(booking=booking, checked_in=checked_in)
    PerformanceSeatingFactory(
        performance=booking.performance, seat_group=ticket.seat_group, price=100
    )
    discount = DiscountFactory(percentage=0)
    discount.performances.set([booking.performance])
    DiscountRequirement(
        number=1, concession_type=ticket.concession_type, discount=discount
    )
