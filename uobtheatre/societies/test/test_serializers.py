import pytest

from uobtheatre.societies.models import Society
from uobtheatre.societies.serializers import SocietySerializer
from uobtheatre.societies.test.factories import SocietyFactory

DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@pytest.mark.django_db
def test_society_serializer():
    society = SocietyFactory()
    data = Society.objects.first()
    serialized_society = SocietySerializer(data)

    assert serialized_society.data == {
        "id": society.id,
        "name": society.name,
        "logo": society.logo.url if society.logo else None,
    }
