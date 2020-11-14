import factory

from uobtheatre.productions.models import (
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    Production,
    Society,
    Venue,
    Warning,
)
from uobtheatre.venues.test.factories import VenueFactory


class SocietyFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)

    class Meta:
        model = Society


class CrewRoleFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=2)

    class Meta:
        model = CrewRole


class CrewMemberFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    role = factory.SubFactory(CrewRoleFactory)

    class Meta:
        model = CrewMember


class CastMemberFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    role = factory.Faker("sentence", nb_words=3)
    profile_picture = factory.django.ImageField(color="blue", use_url=True)

    class Meta:
        model = CastMember


class ProductionFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=3)
    subtitle = factory.Faker("sentence", nb_words=6)
    description = factory.Faker("sentence", nb_words=20)
    society = factory.SubFactory(SocietyFactory)
    poster_image = factory.django.ImageField(color="blue", use_url=True)
    featured_image = factory.django.ImageField(color="blue", use_url=True)
    cover_image = factory.django.ImageField(color="blue", use_url=True)

    # cast = factory.List([factory.SubFactory(CastMemberFactory) for _ in range(5)])
    # crew = factory.List([factory.SubFactory(CrewMemberFactory) for _ in range(5)])

    class Meta:
        model = Production


class PerformanceFactory(factory.django.DjangoModelFactory):

    start = factory.Faker("date_time")
    end = factory.Faker("date_time")
    extra_information = factory.Faker("sentence")
    production = factory.SubFactory(ProductionFactory)
    venue = factory.SubFactory(VenueFactory)

    class Meta:
        model = Performance
