import factory

from uobtheatre.productions.models import (
    Society,
    Production,
    Venue,
    Performance,
)


class SocietyFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)

    class Meta:
        model = Society


class ProductionFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=3)
    subtitle = factory.Faker("sentence", nb_words=6)
    description = factory.Faker("sentence", nb_words=20)
    society = factory.SubFactory(SocietyFactory)
    poster_image = factory.django.ImageField(color="blue", use_url=True)
    featured_image = factory.django.ImageField(color="blue", use_url=True)

    class Meta:
        model = Production


class VenueFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)

    class Meta:
        model = Venue


class PerformanceFactory(factory.django.DjangoModelFactory):

    start = factory.Faker("date_time")
    end = factory.Faker("date_time")
    production = factory.SubFactory(ProductionFactory)
    venue = factory.SubFactory(VenueFactory)

    class Meta:
        model = Performance
