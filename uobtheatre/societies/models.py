from autoslug import AutoSlugField
from django.db import models

from uobtheatre.utils.models import TimeStampedMixin


class Society(TimeStampedMixin, models.Model):
    """A society is a society"""

    name = models.CharField(max_length=255)
    description = models.TextField()
    logo = models.ImageField()
    banner = models.ImageField()

    slug = AutoSlugField(populate_from="name", unique=True, blank=True)

    def __str__(self):
        return self.name
