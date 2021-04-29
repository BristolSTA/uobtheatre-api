from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedMixin(models.Model):
    """Adds created_at and updated_at to a model"""

    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def validate_percentage(percentage):
    # If the percentage is not in the range of 0 to 1
    if not 0 <= percentage <= 1:
        raise ValidationError(
            f"The percentage {percentage} is not in the required range [0, 1]"
        )


class InheritanceCastModel(models.Model):
    """
    An abstract base class that provides a ``real_type`` FK to ContentType.

    For use in trees of inherited models, to be able to downcast
    parent instances to their child types.

    """

    real_type = models.ForeignKey(
        ContentType, editable=False, on_delete=models.RESTRICT
    )

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.real_type = self._get_real_type()
        super(InheritanceCastModel, self).save(*args, **kwargs)

    def _get_real_type(self):
        return ContentType.objects.get_for_model(type(self))

    def cast(self):
        return self.real_type.get_object_for_this_type(pk=self.pk)

    class Meta:
        abstract = True
