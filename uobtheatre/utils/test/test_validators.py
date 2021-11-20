import pytest
from types import SimpleNamespace
from uobtheatre.utils.validators import (
    RequiredFieldsValidator,
    RequiredFieldValidator,
    AndValidator,
    ValidationError,
)

required_a_and_b_parameters = (
    "obj,errors",
    [
        (SimpleNamespace(a=1, b=1), []),
        (
            SimpleNamespace(a=None, b=1),
            [ValidationError(message="a is required", attribute="a")],
        ),
        (
            SimpleNamespace(a=None, b=None),
            [
                ValidationError(message="a is required", attribute="a"),
                ValidationError(message="b is required", attribute="b"),
            ],
        ),
    ],
)


@pytest.mark.parametrize(*required_a_and_b_parameters)
def test_required_fields_validator(obj, errors):
    validator = RequiredFieldsValidator(["a", "b"])
    assert validator.validate(obj) == errors


@pytest.mark.parametrize(*required_a_and_b_parameters)
def test_and_validator(obj, errors):
    validator = AndValidator(RequiredFieldValidator("a"), RequiredFieldValidator("b"))
    assert validator.validate(obj) == errors


def test_and_validator_method():
    validator_1 = RequiredFieldValidator("a")
    validator_2 = RequiredFieldValidator("b")
    assert validator_1 & validator_2 == AndValidator(validator_1, validator_2)
