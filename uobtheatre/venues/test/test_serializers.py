import pytest

from uobtheatre.venues.test.factories import (
    VenueFactory,
)
from uobtheatre.venues.serializers import (
    VenueSerializer,
)
from uobtheatre.venues.models import (
    Venue,
)


DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@pytest.mark.django_db
def test_venue_serializer():
    venue = VenueFactory()
    data = Venue.objects.first()
    serialized_venue = VenueSerializer(data)

    assert serialized_venue.data == {
        "id": venue.id,
        "name": venue.name,
    }
