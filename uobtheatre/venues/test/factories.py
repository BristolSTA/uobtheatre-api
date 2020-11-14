import factory

from uobtheatre.venues.models import SeatGroup, SeatType, Venue


class VenueFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    internal_capacity = factory.Faker("pyint")

    class Meta:
        model = Venue


class SeatTypeFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    is_internal = True

    class Meta:
        model = SeatType


class SeatGroupFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    seat_type = factory.SubFactory(SeatTypeFactory)
    venue = factory.SubFactory(VenueFactory)
    capacity = factory.Faker("pyint")

    class Meta:
        model = SeatGroup
