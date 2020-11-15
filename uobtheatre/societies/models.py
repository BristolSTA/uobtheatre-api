from django.db import models

from uobtheatre.utils.models import SoftDeletionMixin, TimeStampedMixin


class Society(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A society is a society"""

    name = models.CharField(max_length=255)
    logo = models.ImageField()

    def __str__(self):
        return self.name
