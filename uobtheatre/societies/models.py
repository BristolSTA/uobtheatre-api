from autoslug import AutoSlugField
from django.db import models
from django_tiptap.fields import TipTapTextField

from uobtheatre.images.models import Image
from uobtheatre.utils.models import TimeStampedMixin


class Society(TimeStampedMixin, models.Model):
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

    # The id of the square location used for this society's inperson sales
    square_pos_location = models.CharField(max_length=24, blank=True, null=True)
    # This timestamp shows which orders have been synced with the api. Any
    # payments after this timestamp may not be recorded in the api.
    square_pos_sync_date = models.DateTimeField(blank=True, null=True)

    def create_pos_location(self):
        """Create a square location for this society

        This is used for inperson sales of goods (not tickets).
        """
        from uobtheatre.payments.transaction_providers import SquareConfectionery

        location_id = SquareConfectionery.create_society_location(self)
        self.square_pos_location = location_id
        self.save()

    def __str__(self):
        return str(self.name)

    class Meta:
        permissions = (("add_production", "Can add productions for this society"),)
