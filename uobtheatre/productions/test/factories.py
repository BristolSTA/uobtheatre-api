import factory
from django.utils import timezone

from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.productions.models import (
    AudienceWarning,
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    Production,
    ProductionTeamMember,
    Society,
    Venue,
)
from uobtheatre.societies.test.factories import SocietyFactory
from uobtheatre.venues.test.factories import VenueFactory


class ProductionFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=3)
    subtitle = factory.Faker("sentence", nb_words=6)
    description = factory.Faker("sentence", nb_words=20)
    society = factory.SubFactory(SocietyFactory)
    poster_image = factory.SubFactory(ImageFactory)
    featured_image = factory.SubFactory(ImageFactory)
    cover_image = factory.SubFactory(ImageFactory)

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


class ProductionTeamMemberFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    role = factory.Faker("sentence", nb_words=3)
    production = factory.SubFactory(ProductionFactory)

    class Meta:
        model = ProductionTeamMember


class CastMemberFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    role = factory.Faker("sentence", nb_words=3)
    profile_picture = factory.SubFactory(ImageFactory)
    production = factory.SubFactory(ProductionFactory)

    class Meta:
        model = CastMember


class AudienceWarningFactory(factory.django.DjangoModelFactory):
    description = factory.Faker("sentence", nb_words=3)

    class Meta:
        model = AudienceWarning


def create_production(start, end, production_id=None):
    """Create a production with some performances

    Args:
        start (datetime): When the Production (its first Performance) should
            start.
        end (datetime): When the Production (its last Performance) should end.
        production_id (int): Sets the id of Production. If None then a random
            id is created.
            (default None)

    Returns:
        Production: The generated Production.
    """
    if production_id is None:
        production = ProductionFactory()
    else:
        production = ProductionFactory(id=production_id)
    diff = end - start
    for i in range(5):
        time = start + (diff / 5) * i
        PerformanceFactory(start=time, end=time, production=production)
    return production
