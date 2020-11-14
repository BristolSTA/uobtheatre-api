import pytest
import factory

from django.utils import timezone
from datetime import timedelta

from uobtheatre.productions.test.factories import (
    ProductionFactory,
    SocietyFactory,
    PerformanceFactory,
)


DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@pytest.mark.django_db
def test_society_view_get(api_client):

    socTest = SocietyFactory()

    response = api_client.get("/api/v1/societies/")

    socities = [
        {
            "id": socTest.id,
            "name": socTest.name,
        },
    ]

    assert response.status_code == 200
    assert response.json()["results"] == socities


def test_society_view_is_read_only(api_client):

    response = api_client.post("/api/v1/societies/")
    assert response.status_code == 405

    response = api_client.put("/api/v1/societies/")
    assert response.status_code == 405

    response = api_client.delete("/api/v1/societies/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_production_view_get(api_client):

    # Create a fake production
    prod1 = ProductionFactory()
    perf1 = PerformanceFactory(production=prod1)
    perf2 = PerformanceFactory(production=prod1)

    # Get the productions endpoint
    response = api_client.get("/api/v1/productions/")

    performances = [
        {
            "id": performance.id,
            "production": prod1.id,
            "venue": {
                "id": performance.venue.id,
                "name": performance.venue.name,
            },
            "extra_information": performance.extra_information,
            "start": performance.start.isoformat()[:-3] + "00",
            "end": performance.end.isoformat()[:-3] + "00",
        }
        for performance in prod1.performances.all()
    ]

    warnings = [warning.name for warning in prod1.warnings.all()]

    cast = [
        {
            "name": castmember.name,
            "profile_picture": castmember.profile_picture.url,
            "role": castmember.role,
        }
        for castmember in prod1.cast.all()
    ]

    crew = [
        {
            "name": crewmember.name,
            "role": crewmember.role.name,
        }
        for crewmember in prod1.crew.all()
    ]

    # Assert it returns 200 and what is expected
    assert response.status_code == 200
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": prod1.id,
                "name": prod1.name,
                "subtitle": prod1.subtitle,
                "description": prod1.description,
                "society": {"id": prod1.society.id, "name": prod1.society.name},
                "poster_image": "http://testserver" + prod1.poster_image.url,
                "featured_image": "http://testserver" + prod1.featured_image.url,
                "cover_image": "http://testserver" + prod1.cover_image.url,
                "age_rating": prod1.age_rating,
                "facebook_event": prod1.facebook_event,
                "performances": performances,
                "cast": cast,
                "crew": crew,
                "warnings": warnings,
                "start_date": prod1.start_date().strftime(DATE_FORMAT),
                "end_date": prod1.end_date().strftime(DATE_FORMAT),
            },
        ],
    }


@pytest.mark.django_db
def test_production_view_upcoming_productions_action(api_client):

    # Create some productions that are in the past
    production1 = ProductionFactory()
    production2 = ProductionFactory()
    production3 = ProductionFactory()

    for i in range(10):

        PerformanceFactory(
            start=timezone.now() - timedelta(hours=i * 2),
            end=timezone.now() - timedelta(hours=i),
            production=production1,
        )

    # Assert that there are no productions
    response = api_client.get("/api/v1/productions/upcoming_productions/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 0

    # Create some productions that are on going (have started by not ended)
    for i in range(10):
        PerformanceFactory(
            start=timezone.now() - timedelta(hours=i),
            end=timezone.now() + timedelta(hours=i),
            production=production1,
        )

    # Still assert no productions
    response = api_client.get("/api/v1/productions/upcoming_productions/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 0

    # Create some productions that are in the future
    for i in range(10):
        PerformanceFactory(
            start=timezone.now() + timedelta(hours=i * 4),
            end=timezone.now() + timedelta(hours=i * 6),
            production=production1,
        )
        PerformanceFactory(
            start=timezone.now() + timedelta(hours=i),
            end=timezone.now() + timedelta(hours=i * 2),
            production=production2,
        )
        PerformanceFactory(
            start=timezone.now() + timedelta(hours=i * 8),
            end=timezone.now() + timedelta(hours=i * 12),
            production=production3,
        )

    response = api_client.get("/api/v1/productions/upcoming_productions/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 3

    # Check the order
    # The first performance is more in the future so should be returned second
    assert response.json()["results"][0]["id"] == production2.id
    assert response.json()["results"][1]["id"] == production1.id
    assert response.json()["results"][2]["id"] == production3.id
