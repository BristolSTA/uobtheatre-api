import pytest

from uobtheatre.venues.models import Venue
from uobtheatre.venues.serializers import VenueSerializer
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_venue_serializer():
    venue = VenueFactory()
    data = Venue.objects.first()
    serialized_venue = VenueSerializer(data)

    assert serialized_venue.data == {
        "id": venue.id,
        "name": venue.name,
    }
