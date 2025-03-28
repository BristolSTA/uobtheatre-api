import pytest
import pytz

from uobtheatre.addresses.test.factories import AddressFactory
from uobtheatre.utils.validators import ValidationError


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


@pytest.mark.django_db
def test_timezone_without_coordinates():
    address = AddressFactory(latitude=None, longitude=None)
    assert address.timezone == pytz.UTC


@pytest.mark.django_db
def test_timezone_with_coordinates():
    address = AddressFactory(latitude=51.45662710361974, longitude=-2.613237959640326)
    assert address.timezone.zone == "Europe/London"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "what3words, valid, error_message",
    [
        (None, True, None),
        ("///word.word.word", True, None),
        ("word.word.word", False, "The what3words address must start with '///'."),
        (
            "///word.word.word.word",
            False,
            "The what3words address must contain 3 words separated by dots.",
        ),
        (
            "///word.word",
            False,
            "The what3words address must contain 3 words separated by dots.",
        ),
    ],
)
def test_invalid_what3words(what3words, valid, error_message):
    address = AddressFactory()
    address.what3words = what3words

    if valid:
        address.save()
    else:
        with pytest.raises(ValidationError) as excinfo:
            address.save()
        assert str(excinfo.value) == error_message
