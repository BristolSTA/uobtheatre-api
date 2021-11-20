import pytest
from types import SimpleNamespace
from uobtheatre.utils.validators import (
    RequiredFieldsValidator,
    RequiredFieldValidator,
    AndValidator,
)


@pytest.mark.parametrize(
    "obj,is_valid",
    [
        (SimpleNamespace(a=1, b=1), True),
        (SimpleNamespace(a=None, b=1), False),
        (SimpleNamespace(a=None, b=None), False),
    ],
)
def test_and_validator(obj, is_valid):
    validator = RequiredFieldsValidator(["a", "b"])
    assert validator.validate(obj) == is_valid


def test_and_validator_method():
    validator_1 = RequiredFieldValidator("a")
    validator_2 = RequiredFieldValidator("b")
    assert validator_1 & validator_2 == AndValidator(validator_1, validator_2)
