import pytest

from uobtheatre.productions.test.factories import (
    ProductionFactory,
    SocietyFactory,
    PerformanceFactory,
)


@pytest.mark.django_db
def test_production_view_get(api_client):

    # Create a fake production
    prod1 = ProductionFactory()
    prod2 = ProductionFactory()

    performance1 = PerformanceFactory(production=prod2)
    performance2 = PerformanceFactory(production=prod2)

    # Get the productions endpoint
    response = api_client.get("/api/v1/productions/")

    # Assert it returns 200 and what is expected
    assert response.status_code == 200
    assert response.json() == {
        "count": 2,
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
                "performances": [],
            },
            {
                "id": prod2.id,
                "name": prod2.name,
                "subtitle": prod2.subtitle,
                "description": prod2.description,
                "society": {"id": prod2.society.id, "name": prod2.society.name},
                "poster_image": "http://testserver" + prod2.poster_image.url,
                "featured_image": "http://testserver" + prod2.featured_image.url,
                "performances": [
                    {
                        "id": performance1.id,
                        "production": performance1.production.id,
                        "venue": {
                            "id": performance1.venue.id,
                            "name": performance1.venue.name,
                        },
                        "start": performance1.start.isoformat() + "+0000",
                        "end": performance1.end.isoformat() + "+0000",
                    },
                    {
                        "id": performance2.id,
                        "production": performance2.production.id,
                        "venue": {
                            "id": performance2.venue.id,
                            "name": performance2.venue.name,
                        },
                        "start": performance2.start.isoformat() + "+0000",
                        "end": performance2.end.isoformat() + "+0000",
                    },
                ],
            },
        ],
    }
