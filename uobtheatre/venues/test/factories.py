import factory

from uobtheatre.venues.models import SeatGroup, Venue
from uobtheatre.addresses.test.factories import AddressFactory


class VenueFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    description = factory.Faker("paragraph", nb_sentences=3)
    internal_capacity = factory.Faker("pyint")
    address = factory.SubFactory(AddressFactory)

    class Meta:
        model = Venue


class SeatGroupFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    venue = factory.SubFactory(VenueFactory)
    capacity = factory.Faker("pyint")

    class Meta:
        model = SeatGroup
