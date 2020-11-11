import pytest

from uobtheatre.productions.test.factories import (
    ProductionFactory,
    SocietyFactory,
    VenueFactory,
    PerformanceFactory,
)
from uobtheatre.productions.serializers import (
    ProductionSerializer,
    SocietySerializer,
    VenueSerializer,
    PerformanceSerializer,
)
from uobtheatre.productions.models import (
    Production,
    Performance,
    Society,
    Venue,
)


@pytest.mark.django_db
def test_society_serializer():
    society = SocietyFactory()
    data = Society.objects.first()
    serialized_society = SocietySerializer(data)

    assert serialized_society.data == {
        "id": society.id,
        "name": society.name,
    }


@pytest.mark.django_db
def test_production_no_performances_serializer():
    production = ProductionFactory()
    data = Production.objects.first()
    serialized_prod = ProductionSerializer(data)

    assert serialized_prod.data == {
        "id": production.id,
        "name": production.name,
        "subtitle": production.subtitle,
        "description": production.description,
        "society": {
            "id": production.society.id,
            "name": production.society.name,
        },
        "poster_image": production.poster_image.url,
        "featured_image": production.featured_image.url,
        "performances": [],
    }


@pytest.mark.django_db
def test_production_with_performances_serializer():
    production = ProductionFactory()
    data = Production.objects.first()
    serialized_prod = ProductionSerializer(data)

    performance1 = PerformanceFactory(production=production)
    performance2 = PerformanceFactory(production=production)

    assert serialized_prod.data == {
        "id": production.id,
        "name": production.name,
        "subtitle": production.subtitle,
        "description": production.description,
        "society": {
            "id": production.society.id,
            "name": production.society.name,
        },
        "poster_image": production.poster_image.url,
        "featured_image": production.featured_image.url,
        "performances": [
            {
                "id": performance1.id,
                "production": performance1.production.id,
                "venue": performance1.venue.id,
                "date": performance1.date.isoformat() + "+0000",
            },
            {
                "id": performance2.id,
                "production": performance2.production.id,
                "venue": performance2.venue.id,
                "date": performance2.date.isoformat() + "+0000",
            },
        ],
    }


@pytest.mark.django_db
def test_venue_serializer():
    venue = VenueFactory()
    data = Venue.objects.first()
    serialized_venue = VenueSerializer(data)

    assert serialized_venue.data == {
        "id": venue.id,
        "name": venue.name,
    }


@pytest.mark.django_db
def test_performance_serializer():
    performace = PerformanceFactory()
    data = Performance.objects.first()
    serialized_performance = PerformanceSerializer(data)

    assert serialized_performance.data == {
        "id": performace.id,
        "production": performace.production.id,
        "venue": performace.venue.id,
        "date": performace.date.isoformat() + "+0000",
    }
