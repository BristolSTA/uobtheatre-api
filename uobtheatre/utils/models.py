"""
Utils for uobtheatre modles
"""


from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedMixin(models.Model):
    """Adds created_at and updated_at to a model

    Both created at and updated at are automatically set.
    """

    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def validate_percentage(percentage):
    """Validate a given percentage value

    A percentage value can only be between 0 and 1. If this is not the case a
    ValidationError is raised

    Args:
        (float): The percentage value to validate

    Raises:
        ValidationError: If the value is not valid
    """
    if not 0 <= percentage <= 1:
        raise ValidationError(
            f"The percentage {percentage} is not in the required range [0, 1]"
        )


class Draft(models.Model):
    """Adds support for drafts to model

    A draft is a model which can be created without the required fields and
    then saved later if all the requirements are met.
    """

    draft = models.BooleanField(default=True)

    def __init_subclass__(cls):
        if not hasattr(cls, "required_fields"):
            raise ValueError(
                "When using a draft model you must define the required_fields"
            )

    def publish(self):
        print(self.required_fields)
