from autoslug import AutoSlugField
from django.db import models
from django_tiptap.fields import TipTapTextField

from uobtheatre.images.models import Image
from uobtheatre.utils.models import TimeStampedMixin


class Society(TimeStampedMixin, models.Model):
    """Model for a group which puts on Productions."""

    name = models.CharField(max_length=255)
    description = TipTapTextField()
    logo = models.ForeignKey(
        Image, on_delete=models.RESTRICT, related_name="society_logos"
    )
    banner = models.ForeignKey(
        Image, on_delete=models.RESTRICT, related_name="society_banners"
    )

    slug = AutoSlugField(populate_from="name", unique=True, blank=True)

    def __str__(self):
        return str(self.name)
