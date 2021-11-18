from __future__ import annotations
import abc
from typing import Union, Callable, Any

field_validator_types = Union[Validator, Callable]


class Validator:
    def __init__(self, **attribute_validators):
        self.attribute_validators = attribute_validators
        self.errors = []

    def is_valid(self):
        self.errors = []
        self.validate()

    def run_validator(self, instance, validator: field_validator_types, attribute: str):
        self.check_validator_type(validator)
        attribute_value = instance.getattribute(attribute)
        if isinstance(validator, Validator):
            validator.validate(instance.getattribute(attribute))
        if callable(validator):
            validator(attribute_value, instance)

    def check_validator_type(self, validator: Any):
        if not (isinstance(validator, Callable) or isinstance(validator, Validator)):
            raise ValueError("Invalid type of validator")

    def validate(self, instance) -> bool:
        for attribute, validators in self.attribute_validators.items():
            # If the validator is a list of validators, use each
            if isinstance(validators, list):
                for validator in validators:
                    self.run_validator(instance, validator, attribute)
            self.run_validator(instance, validators, attribute)

    def __and2__(self, other):
        new_attribute_validators = {}
        for attribute, value in self.attribute_validators.items():
            new_attribute_validators[attribute] = (
                value if isinstance(value, list) else [value]
            )

        for attribute, value in other.attribute_validators.items():
            new_attribute_validators[attribute] = new_attribute_validators.get(
                "attribute", []
            ).extend(value if isinstance(value, list) else [value])

        return Validator(**new_attribute_validators)


class RequiredFieldVaidator(Validator):
    def __init__(self, attribute):
        self.attibute = attribute

    def validate(self, instance):
        return instance.getattribute(self.attibute) != None


class RequiredFieldsValidator(Validator):
    def __init__(self, required_attributes):
        self.attribute_validators = {
            attribute: RequiredFieldVaidator(attribute)
            for attribute in required_attributes
        }
