from __future__ import annotations
import abc
from typing import Union, Callable, Any
from dataclasses import dataclass


@dataclass
class Validator(abc.ABC):
    @abc.abstractmethod
    def validate(self, instance):
        pass

    def __and__(self, other):
        return AndValidator(self, other)


@dataclass
class AttributeValidator(Validator):
    attibute: str

    @abc.abstractmethod
    def validate_attribute(self, value):
        pass

    def validate(self, instance):
        attribute_value = getattr(instance, self.attibute)
        return self.validate_attribute(attribute_value)


@dataclass
class RequiredFieldValidator(AttributeValidator):
    def validate_attribute(self, value):
        return value is not None


@dataclass
class AndValidator(Validator):
    def __init__(self, *validators):
        self.validators = validators

    def validate(self, instance):
        return all(validator.validate(instance) for validator in self.validators)


@dataclass
class RequiredFieldsValidator(AndValidator):
    def __init__(self, required_attributes):
        self.validators = [
            RequiredFieldValidator(field) for field in required_attributes
        ]
