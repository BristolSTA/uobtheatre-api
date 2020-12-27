import pytest

from uobtheatre.addresses.test.factories import AddressFactory


@pytest.mark.parametrize(
    "building_name, building_number, output",
    [
        (
            "The Richmond Building",
            "105",
            "The Richmond Building, 105, Queens Road, Bristol, BS1 1AE",
        ),
        (
            "The Richmond Building",
            None,
            "The Richmond Building, Queens Road, Bristol, BS1 1AE",
        ),
        (None, "105", "105, Queens Road, Bristol, BS1 1AE"),
        (None, None, "Queens Road, Bristol, BS1 1AE"),
    ],
)
@pytest.mark.django_db
def test_address_to_string(building_name, building_number, output):
    address = AddressFactory(
        building_name=building_name,
        building_number=building_number,
        street="Queens Road",
        city="Bristol",
        postcode="BS1 1AE",
    )

    assert str(address) == output
