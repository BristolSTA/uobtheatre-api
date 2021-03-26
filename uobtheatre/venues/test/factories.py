import factory

from uobtheatre.addresses.test.factories import AddressFactory
from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.venues.models import Seat, SeatGroup, Venue


class VenueFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    description = factory.Faker("paragraph", nb_sentences=3)
    internal_capacity = factory.Faker("pyint")
    address = factory.SubFactory(AddressFactory)
    image = factory.SubFactory(ImageFactory)

    class Meta:
        model = Venue


class SeatGroupFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    venue = factory.SubFactory(VenueFactory)
    capacity = factory.Faker("pyint")

    class Meta:
        model = SeatGroup


class SeatFactory(factory.django.DjangoModelFactory):
    row = factory.Faker("bothify", text="???")
    number = factory.Faker("bothify", text="###")

    class Meta:
        model = Seat
