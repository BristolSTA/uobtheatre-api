import pytest

from uobtheatre.addresses.test.factories import AddressFactory


@pytest.mark.django_db
def test_address_to_string():
    address = AddressFactory(street="Richmond Hill", city="Bristol", postcode="BS1 1AE")

    assert str(address) == f"Richmond Hill, Bristol, BS1 1AE"
