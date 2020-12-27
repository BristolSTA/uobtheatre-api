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
            "description": venueTest.description,
            "address": {
                "building_name": venueTest.address.building_name,
                "building_number": venueTest.address.building_number,
                "street": venueTest.address.street,
                "city": venueTest.address.city,
                "postcode": venueTest.address.postcode,
                "latitude": float(venueTest.address.latitude),
                "longitude": float(venueTest.address.longitude),
            },
        },
    ]

    assert response.status_code == 200
    assert response.json()["results"] == venues
