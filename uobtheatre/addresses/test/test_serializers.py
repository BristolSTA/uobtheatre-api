import pytest

from uobtheatre.addresses.models import Address
from uobtheatre.addresses.serializers import AddressSerializer
from uobtheatre.addresses.test.factories import AddressFactory


@pytest.mark.django_db
def test_address_serializer():
    address = AddressFactory()
    data = Address.objects.first()
    serialized_address = AddressSerializer(data)

    assert serialized_address.data == {
        "street": address.street,
        "city": address.city,
        "postcode": address.postcode,
        "latitude": float(address.latitude),
        "longitude": float(address.longitude),
    }
