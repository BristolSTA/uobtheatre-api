import factory

from uobtheatre.venues.models import Venue


class VenueFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    internal_capacity = factory.Faker("pyint")

    class Meta:
        model = Venue
