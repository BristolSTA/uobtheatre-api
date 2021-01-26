from django.db import models

from uobtheatre.utils.models import TimeStampedMixin


class Society(models.Model, TimeStampedMixin):
    """A society is a society"""

    name = models.CharField(max_length=255)
    description = models.TextField()
    logo = models.ImageField()
    banner = models.ImageField()

    def __str__(self):
        return self.name
