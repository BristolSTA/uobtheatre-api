from autoslug import AutoSlugField
from django.db import models
from django_tiptap.fields import TipTapTextField

from uobtheatre.images.models import Image
from uobtheatre.utils.models import BaseModel, TimeStampedMixin


class Society(BaseModel, TimeStampedMixin):
    """Model for a group which puts on Productions."""

    name = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from="name", unique=True, blank=True)
    description = TipTapTextField()
    logo = models.ForeignKey(
        Image, on_delete=models.RESTRICT, related_name="society_logos"
    )
    banner = models.ForeignKey(
        Image, on_delete=models.RESTRICT, related_name="society_banners"
    )

    website = models.CharField(max_length=255, blank=True, null=True)
    contact = models.CharField(max_length=255, blank=True, null=True)

    members = models.ManyToManyField("users.User", related_name="societies", blank=True)

    def __str__(self):
        return str(self.name)

    class Meta:
        permissions = (("add_production", "Can add productions for this society"),)
