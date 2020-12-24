import pytest

from uobtheatre.addresses.test.factories import AddressFactory


@pytest.mark.django_db
def test_address_serializer():
    address = AddressFactory()

    assert str(address) == f"{address.street}, {address.city}, {address.postcode}"
