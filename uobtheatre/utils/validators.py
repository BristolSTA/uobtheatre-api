from __future__ import annotations

import abc
import operator
from dataclasses import dataclass
from functools import reduce
from typing import Generator, Optional

from django.core.exceptions import ValidationError as DjangoValidationError

from uobtheatre.utils import exceptions
from uobtheatre.utils.form_validators import OptionalSchemeURLValidator


class ValidationErrors(exceptions.GQLExceptions):
    pass


@dataclass  # type: ignore
class ValidationError(exceptions.MutationException):
    """
    Hold an error result from the validate method of a validator.
    """

    message: str
    attribute: Optional[str] = None

    def resolve(self):
        if self.attribute:
            return [
                exceptions.FieldError(
                    field=self.attribute, code=400, message=self.message
                )
            ]
        return [exceptions.NonFieldError(code=400, message=self.message)]


@dataclass  # type: ignore
class Validator(abc.ABC):
    """
    Baseclass for a validator. This requires a validate method which returrns a
    list of errors.
    Validators can be combined with the & operator.
    """

    @abc.abstractmethod
    def validate(self, instance) -> Optional[ValidationErrors]:
        pass

    def __and__(self, other):
        return AndValidator(self, other)

    @staticmethod
    def combine_errors(generator: Generator) -> Optional[ValidationErrors]:
        """
        Given a generator of ValidationErrors combine all the errors in those
        errors into a flat list.
        This is handy for combining the result of validate on a list of
        validators. E.g.
        ```
        combine_errors(
            validator.validate(obj) for validator in validators
        )

        Args:
            generator: A generator of ValidationErrors.

        Returns:
            ValidationErrors: A ValidationErrors object, containing all the
            errors. If no errors are in of the ValidationErrors in the
            generator then None is returned.
        ```
        """
        errors = reduce(
            operator.add, (filter(None, generator)), ValidationErrors(exceptions=[])
        )
        if not errors:
            return None
        return errors

    def __call__(self, value):
        errors = self.validate(value)
        if errors:
            raise errors


@dataclass  # type: ignore
class AttributeValidator(Validator):
    """
    The base class for a validator which validates a single attribute
    """

    attribute: str

    @abc.abstractmethod
    def validate_attribute(self, value) -> Optional[ValidationErrors]:
        pass

    def validate(self, instance) -> Optional[ValidationErrors]:
        attribute_value = getattr(instance, self.attribute)
        return self.validate_attribute(attribute_value)

    def __call__(self, value):
        errors = self.validate_attribute(value)
        if errors:
            raise errors


@dataclass
class RequiredFieldValidator(AttributeValidator):
    """
    A validator that checks its required attribute is provided (not null).
    """

    def validate_attribute(self, value) -> Optional[ValidationErrors]:
        if value is None:
            return ValidationErrors(
                exceptions=[
                    ValidationError(
                        message="Required",
                        attribute=self.attribute,
                    )
                ]
            )
        return None


@dataclass
class UrlValidator(AttributeValidator):
    """
    A validator that checks its required attribute is provided (not null).
    """

    def validate_attribute(self, value):
        validate = OptionalSchemeURLValidator()
        try:
            validate(value)
        except DjangoValidationError:
            return ValidationErrors(
                exceptions=[
                    ValidationError(
                        message=f"{self.attribute.replace('_', ' ')} is not a valid url",
                        attribute=self.attribute,
                    )
                ]
            )
        return None


@dataclass
class AndValidator(Validator):
    """Combines multiple validators together to ensure they all pass"""

    def __init__(self, *validators):
        self.validators = validators
        super().__init__()

    def validate(self, instance):
        return self.combine_errors(
            validator.validate(instance) for validator in self.validators
        )


@dataclass
class RequiredFieldsValidator(AndValidator):
    def __init__(self, required_attributes):
        super().__init__(
            *[RequiredFieldValidator(field) for field in required_attributes]
        )


@dataclass
class PercentageValidator(AttributeValidator):
    """
    A validator that checks its required attribute is a percentage.
    """

    def __init__(self, attribute="percentage"):
        super().__init__(attribute=attribute)

    def validate_attribute(self, value):
        if value < 0 or value > 1:
            return ValidationErrors(
                exceptions=[
                    ValidationError(
                        message=f"{value} is not a valid percentage. A percenage must be between 0 and 1",
                        attribute=self.attribute,
                    )
                ]
            )
        return None


@dataclass
class RelatedObjectsValidator(Validator):
    """
    Validate all instances of a related attribute. Applies the provided
    validator to all attributes and returns all errors combined.

    If a min_number is provided then the validator will fail if there are fewer
    than this number of related objects. E.g. Productions require at least 1
    performance.
    """

    def __init__(self, attribute: str, validator, min_number: int = None):
        self.attribute = attribute
        self.validator = validator
        self.min_number = min_number
        super().__init__()

    def _get_attributes(self, instance):
        return getattr(instance, self.attribute).all()

    def _validate_number(self, instance) -> Optional[ValidationError]:
        """
        Validate the realated attribute has at least min_number objects
        """
        if (
            self.min_number is not None
            and not self._get_attributes(instance).count() >= self.min_number
        ):
            verb = "are" if self.min_number > 1 else "is"
            return ValidationError(
                message=f"At least {self.min_number} {self.attribute} {verb} required.",
                attribute=self.attribute,
            )
        return None

    def validate(self, instance) -> Optional[ValidationErrors]:
        errors = self.combine_errors(
            self.validator.validate(related_instance)
            for related_instance in self._get_attributes(instance)
        ) or ValidationErrors(exceptions=[])
        if number_error := self._validate_number(instance):
            errors.add_exception(number_error)

        if not errors:
            return None
        return errors
