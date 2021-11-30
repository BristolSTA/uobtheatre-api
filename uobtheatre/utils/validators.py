from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Generator, Optional

from uobtheatre.utils import exceptions


@dataclass
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
    def validate(self, instance) -> list[ValidationError]:
        pass

    def __and__(self, other):
        return AndValidator(self, other)

    @staticmethod
    def all_errors(generator: Generator):
        """
        Given a generator (for a list of list of errors) combine all the errors
        into a flat list.
        This is handy for combining validate on a list of validators. E.g.
        ```
        all_errors(
            validator.validate(obj) for validator in validators
        )
        ```
        """
        return [error for sublist in generator for error in sublist]


@dataclass  # type: ignore
class AttributeValidator(Validator):
    """
    The base class for a validator which validates a single attribute
    """

    attribute: str

    @abc.abstractmethod
    def validate_attribute(self, value) -> list[ValidationError]:
        pass

    def validate(self, instance) -> list[ValidationError]:
        attribute_value = getattr(instance, self.attribute)
        return self.validate_attribute(attribute_value)


@dataclass
class RequiredFieldValidator(AttributeValidator):
    """
    A validator that checks its required attribute is provided (not null).
    """

    def validate_attribute(self, value):
        if value is None:
            return [
                ValidationError(
                    message=f"{self.attribute.replace('_', ' ')} is required",
                    attribute=self.attribute,
                )
            ]
        return []


@dataclass
class AndValidator(Validator):
    def __init__(self, *validators):
        self.validators = validators

    def validate(self, instance):
        return self.all_errors(
            validator.validate(instance) for validator in self.validators
        )


@dataclass
class RequiredFieldsValidator(AndValidator):
    def __init__(self, required_attributes):
        super().__init__(
            *[RequiredFieldValidator(field) for field in required_attributes]
        )


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

    def validate(self, instance) -> list[ValidationError]:
        errors = self.all_errors(
            self.validator.validate(related_instance)
            for related_instance in self._get_attributes(instance)
        )
        if number_error := self._validate_number(instance):
            errors.append(number_error)
        return errors
