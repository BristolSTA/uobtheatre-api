import pytest

from uobtheatre.productions.test.factories import (
    ProductionFactory,
    SocietyFactory,
)
from uobtheatre.productions.serializers import (
    ProductionSerializer,
    SocietySerializer,
)
from uobtheatre.productions.models import (
    Production,
    Society,
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
def test_prodction_serializer():
    production = ProductionFactory()
    data = Production.objects.first()
    serialized_prod = ProductionSerializer(data)

    assert serialized_prod.data == {
        "id": production.id,
        "name": production.name,
        "society": {
            "id": production.society.id,
            "name": production.society.name,
        },
    }
