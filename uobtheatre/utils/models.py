from django.db import models


class TimeStampedMixin:
    """Adds created_at and updated_at to a model"""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
