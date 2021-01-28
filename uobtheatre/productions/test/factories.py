import factory
from django.utils import timezone

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


class ProductionFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=3)
    subtitle = factory.Faker("sentence", nb_words=6)
    description = factory.Faker("sentence", nb_words=20)
    society = factory.SubFactory(SocietyFactory)
    poster_image = factory.django.ImageField(color="blue", use_url=True)
    featured_image = factory.django.ImageField(color="blue", use_url=True)
    cover_image = factory.django.ImageField(color="blue", use_url=True)

    class Meta:
        model = Production


class PerformanceFactory(factory.django.DjangoModelFactory):

    doors_open = factory.Faker("date_time", tzinfo=timezone.get_current_timezone())
    start = factory.Faker("date_time", tzinfo=timezone.get_current_timezone())
    end = factory.Faker("date_time", tzinfo=timezone.get_current_timezone())
    extra_information = factory.Faker("sentence")
    description = factory.Faker("sentence")
    disabled = factory.Faker("boolean")
    production = factory.SubFactory(ProductionFactory)
    venue = factory.SubFactory(VenueFactory)

    class Meta:
        model = Performance


class CrewRoleFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=2)

    class Meta:
        model = CrewRole


class CrewMemberFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    role = factory.SubFactory(CrewRoleFactory)
    production = factory.SubFactory(ProductionFactory)

    class Meta:
        model = CrewMember


class CastMemberFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    role = factory.Faker("sentence", nb_words=3)
    profile_picture = factory.django.ImageField(color="blue", use_url=True)
    production = factory.SubFactory(ProductionFactory)

    class Meta:
        model = CastMember


class WarningFactory(factory.django.DjangoModelFactory):
    warning = factory.Faker("sentence", nb_words=3)

    class Meta:
        model = Warning
