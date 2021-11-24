from types import SimpleNamespace

import pytest

from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.utils.validators import (
    AndValidator,
    RelatedObjectsValidator,
    RequiredFieldsValidator,
    RequiredFieldValidator,
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "number_of_related_objects,validator_min_number,mock_validator_response,expected_errors",
    [
        (1, 1, [], []),
        (
            1,
            2,
            [],
            [
                ValidationError(
                    message="At least 2 performances are required.",
                    attribute="performances",
                )
            ],
        ),
        (
            2,
            None,
            [
                ValidationError(
                    message="Some error",
                    attribute="some_field",
                )
            ],
            [
                ValidationError(
                    message="Some error",
                    attribute="some_field",
                ),
                ValidationError(
                    message="Some error",
                    attribute="some_field",
                ),
            ],
        ),
    ],
)
def test_realted_objects_validator_min_number(
    number_of_related_objects,
    validator_min_number,
    mock_validator_response,
    expected_errors,
):
    production = ProductionFactory()
    _ = [
        PerformanceFactory(production=production)
        for _ in range(number_of_related_objects)
    ]

    class MockValidator:
        def validate(self, *_, **__):
            return mock_validator_response

    errors = RelatedObjectsValidator(
        "performances", MockValidator(), min_number=validator_min_number
    ).validate(production)

    assert errors == expected_errors
