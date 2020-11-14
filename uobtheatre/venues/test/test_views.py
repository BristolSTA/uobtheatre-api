import pytest

from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_venue_view_get(api_client):

    venueTest = VenueFactory()

    response = api_client.get("/api/v1/venues/")

    venues = [
        {
            "id": venueTest.id,
            "name": venueTest.name,
        },
    ]

    assert response.status_code == 200
    assert response.json()["results"] == venues
