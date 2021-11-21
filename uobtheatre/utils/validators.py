from __future__ import annotations
import abc
from typing import Generator, Union, Callable, Any, Optional
from dataclasses import dataclass
from uobtheatre.utils import exceptions

import graphene


@dataclass
class ValidationError(exceptions.MutationException):
    message: str
    attribute: Optional[str] = None

    def resolve(self):
        if self.attribute:
            return exceptions.FieldError(
                field=self.attribute, code=400, message=self.message
            )
        return exceptions.NonFieldError(code=400, message=self.message)


"""
        submit_draft
        approve_pending -> approved (new)
        publish_approved -> if they can edit
"""


class ValidationErrorNode(graphene.ObjectType):
    message = graphene.String(required=True)
    attribute = graphene.String()


@dataclass
class Validator(abc.ABC):
    @abc.abstractmethod
    def validate(self, instance) -> list[ValidationError]:
        pass

    def __and__(self, other):
        return AndValidator(self, other)

    @staticmethod
    def all_errors(generator: Generator):
        errors_lists = [errors for errors in generator]
        return [error for sublist in errors_lists for error in sublist]


@dataclass
class AttributeValidator(Validator):
    attribute: str

    @abc.abstractmethod
    def validate_attribute(self, value) -> list[ValidationError]:
        pass

    def validate(self, instance) -> list[ValidationError]:
        attribute_value = getattr(instance, self.attribute)
        return self.validate_attribute(attribute_value)


@dataclass
class RequiredFieldValidator(AttributeValidator):
    def validate_attribute(self, value):
        if value is None:
            return [
                ValidationError(
                    message=f"{self.attribute} is required", attribute=self.attribute
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
        self.validators = [
            RequiredFieldValidator(field) for field in required_attributes
        ]
