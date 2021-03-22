from autoslug import AutoSlugField
from django.db import models

from uobtheatre.images.models import Image
from uobtheatre.utils.models import TimeStampedMixin


class Society(TimeStampedMixin, models.Model):
    """A society is a society"""

    name = models.CharField(max_length=255)
    description = models.TextField()
    logo = models.ForeignKey(
        Image, on_delete=models.RESTRICT, related_name="society_logos"
    )
    banner = models.ForeignKey(
        Image, on_delete=models.RESTRICT, related_name="society_banners"
    )

    slug = AutoSlugField(populate_from="name", unique=True, blank=True)

    def __str__(self):
        return self.name
