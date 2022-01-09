from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.utils.validators import (
    AndValidator,
    PercentageValidator,
    RelatedObjectsValidator,
    RequiredFieldsValidator,
    RequiredFieldValidator,
    UrlValidator,
    ValidationError,
    ValidationErrors,
    Validator,
)


@pytest.mark.parametrize(
    "obj, field, output",
    [
        (SimpleNamespace(a=0, b=2), "a", None),
        (SimpleNamespace(field="abc"), "field", None),
        (SimpleNamespace(field=""), "field", None),
        (
            SimpleNamespace(field=None),
            "field",
            ValidationErrors(
                exceptions=[ValidationError(attribute="field", message="Required")]
            ),
        ),
    ],
)
def test_required_field_validator(obj, field, output):
    validator = RequiredFieldValidator(field)
    assert validator.validate(obj) == output


required_a_and_b_parameters = (
    "obj,errors",
    [
        (SimpleNamespace(a_field=1, b=1), None),
        (
            SimpleNamespace(a_field=None, b=1),
            ValidationErrors(
                exceptions=[ValidationError(message="Required", attribute="a_field")]
            ),
        ),
        (
            SimpleNamespace(a_field=None, b=1),
            ValidationErrors(
                exceptions=[ValidationError(message="Required", attribute="a_field")]
            ),
        ),
        (
            SimpleNamespace(a_field=None, b=None),
            ValidationErrors(
                exceptions=[
                    ValidationError(message="Required", attribute="a_field"),
                    ValidationError(message="Required", attribute="b"),
                ]
            ),
        ),
    ],
)


@pytest.mark.parametrize(*required_a_and_b_parameters)
def test_required_fields_validator(obj, errors):
    validator = RequiredFieldsValidator(["a_field", "b"])
    assert validator.validate(obj) == errors


@pytest.mark.parametrize(*required_a_and_b_parameters)
def test_and_validator(obj, errors):
    validator = AndValidator(
        RequiredFieldValidator("a_field"), RequiredFieldValidator("b")
    )
    assert validator.validate(obj) == errors


def test_and_validator_method():
    validator_1 = RequiredFieldValidator("a_field")
    validator_2 = RequiredFieldValidator("b")
    assert validator_1 & validator_2 == AndValidator(validator_1, validator_2)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "number_of_related_objects,validator_min_number,mock_validator_response,expected_errors",
    [
        (1, 1, None, None),
        (
            1,
            2,
            None,
            ValidationErrors(
                exceptions=[
                    ValidationError(
                        message="At least 2 performances are required.",
                        attribute="performances",
                    )
                ]
            ),
        ),
        (
            2,
            None,
            ValidationErrors(
                exceptions=[
                    ValidationError(
                        message="Some error",
                        attribute="some_field",
                    )
                ]
            ),
            ValidationErrors(
                exceptions=[
                    ValidationError(
                        message="Some error",
                        attribute="some_field",
                    ),
                    ValidationError(
                        message="Some error",
                        attribute="some_field",
                    ),
                ]
            ),
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


@pytest.mark.parametrize(
    "percentage,error",
    [
        (0, None),
        (1, None),
        (1.0, None),
        ("1", "A percentage must be a valid number"),
        (1.1, "1.10 is not a valid percentage. A percentage must be between 0 and 1"),
        (2, "2.00 is not a valid percentage. A percentage must be between 0 and 1"),
        (
            2.22222222,
            "2.22 is not a valid percentage. A percentage must be between 0 and 1",
        ),
        (-0.1, "-0.10 is not a valid percentage. A percentage must be between 0 and 1"),
        (-0.1, "-0.10 is not a valid percentage. A percentage must be between 0 and 1"),
    ],
)
def test_percentage_validator(percentage, error):
    validator = PercentageValidator()
    if not error:
        validator(percentage)
    else:
        with pytest.raises(ValidationErrors) as exception:
            validator(percentage)
        assert len(exception.value.exceptions) == 1
        assert exception.value.exceptions[0].message == error
        assert exception.value.exceptions[0].attribute == "percentage"


@pytest.mark.parametrize(
    "url,is_valid",
    [
        ("https://", False),
        ("https://abc", False),
        ("https://abc.com", True),
        ("www.abc.com", True),
        ("http://www.abc.com", True),
    ],
)
def test_url_validator(url, is_valid):
    obj = SimpleNamespace(url=url)
    response = UrlValidator("url").validate(obj)

    if is_valid:
        assert response is None
    else:
        assert len(response.exceptions) == 1
        assert response.exceptions[0].message == "url is not a valid url"


@pytest.mark.parametrize(
    "has_errors",
    [True, False],
)
def test_call_validator(has_errors):
    class MockValidator(Validator):
        validate = MagicMock(
            return_value=None
            if not has_errors
            else ValidationErrors(exceptions=[ValidationError(message="Some error")])
        )

    validator = MockValidator()
    if has_errors:
        with pytest.raises(ValidationErrors):
            validator("abc")
    else:
        validator("abc")

    validator.validate.assert_called_once_with("abc")
