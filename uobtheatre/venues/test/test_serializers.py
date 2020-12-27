import pytest

from uobtheatre.venues.models import Venue
from uobtheatre.venues.serializers import VenueSerializer, FullVenueSerializer
from uobtheatre.venues.test.factories import VenueFactory

from uobtheatre.addresses.serializers import AddressSerializer


@pytest.mark.django_db
def test_full_venue_serializer():
    venue = VenueFactory()
    data = Venue.objects.first()
    serialized_venue = FullVenueSerializer(data)

    assert serialized_venue.data == {
        "id": venue.id,
        "name": venue.name,
        "description": venue.description,
        "address": {
            "street": venue.address.street,
            "building_name": venue.address.building_name,
            "building_number": venue.address.building_number,
            "city": venue.address.city,
            "postcode": venue.address.postcode,
            "latitude": float(venue.address.latitude),
            "longitude": float(venue.address.longitude),
        },
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
