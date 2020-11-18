import factory

from uobtheatre.venues.models import SeatGroup, Venue


class VenueFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    internal_capacity = factory.Faker("pyint")

    class Meta:
        model = Venue


class SeatGroupFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    venue = factory.SubFactory(VenueFactory)
    capacity = factory.Faker("pyint")

    class Meta:
        model = SeatGroup
