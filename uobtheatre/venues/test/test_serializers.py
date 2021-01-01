import pytest

from uobtheatre.addresses.serializers import AddressSerializer
from uobtheatre.venues.models import Venue
from uobtheatre.venues.serializers import FullVenueSerializer, VenueSerializer
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_full_venue_serializer():
    venue = VenueFactory()
    data = Venue.objects.first()
    serialized_venue = FullVenueSerializer(data)

    assert serialized_venue.data == {
        "id": venue.id,
        "name": venue.name,
        "description": venue.description,
        "image": venue.image.url,
        "address": {
            "street": venue.address.street,
            "building_name": venue.address.building_name,
            "building_number": venue.address.building_number,
            "city": venue.address.city,
            "postcode": venue.address.postcode,
            "latitude": float(venue.address.latitude),
            "longitude": float(venue.address.longitude),
        },
        "publicly_listed": venue.publicly_listed,
        "slug": venue.slug,
    }


@pytest.mark.django_db
def test_venue_serializer():
    venue = VenueFactory()
    data = Venue.objects.first()
    serialized_venue = VenueSerializer(data)

    assert serialized_venue.data == {
        "id": venue.id,
        "name": venue.name,
        "publicly_listed": venue.publicly_listed,
        "slug": venue.slug,
    }
