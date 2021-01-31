from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedMixin:
    """Adds created_at and updated_at to a model"""

    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)


def validate_percentage(percentage):
    # If the percentage is not in the range of 0 to 1
    if not 0 <= percentage <= 1:
        raise ValidationError(
            f"The percentage {percentage} is not in the required range [0, 1]"
        )
