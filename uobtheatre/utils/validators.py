from __future__ import annotations
import abc
from typing import Union, Callable, Any

field_validator_types = Union[Validator, Callable]


class Validator(abc.ABC):
    @abc.abstractmethod
    def validate(self, instance):
        pass

    def __and2__(self, other):
        return AndValidator(self, other)


class AttributeValidator(abc.ABC):
    def __init__(self, attribute: str) -> None:
        self.attibute = attribute

    @abc.abstractmethod
    def validate_attribute(self, value):
        pass

    def validate(self, instance):
        attribute_value = getattr(instance, self.attibute)
        self.validate_attribute(attribute_value)


class RequiredFieldValidator(AttributeValidator):
    def validate_attribute(self, value):
        return value is not None


class AndValidator(Validator):
    def __init__(self, *validators):
        self.validators = validators

    def validate(self, instance):
        return all(validator.validate(instance) for validator in self.validators)


class RequiredFieldsValidator(AndValidator):
    def __init__(self, required_attributes):
        self.validators = [
            RequiredFieldValidator(field) for field in required_attributes
        ]
