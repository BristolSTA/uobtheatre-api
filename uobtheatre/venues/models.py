"""
Models for venues.
"""

from autoslug import AutoSlugField
from django.apps import apps
from django.db import models
from django_tiptap.fields import TipTapTextField

from uobtheatre.addresses.models import Address
from uobtheatre.images.models import Image
from uobtheatre.utils.models import BaseModel, TimeStampedMixin


class Seat(models.Model):
    """The model for a seat

    A seat is a single spot in a Venue which only one User can book per
    performance. In most cases this is literally a seat.
    """

    row = models.CharField(max_length=5, null=True, blank=True)
    number = models.CharField(max_length=5, null=True, blank=True)


class Venue(TimeStampedMixin, BaseModel):
    """The model for a venue

    A Venue is a place where Performances can take place.
    """

    name = models.CharField(max_length=255)
    internal_capacity = models.PositiveSmallIntegerField()
    description = TipTapTextField(null=True, blank=True)
    accessibility_info = models.TextField(null=True, blank=True)
    address = models.ForeignKey(Address, on_delete=models.CASCADE)
    image = models.ForeignKey(Image, on_delete=models.RESTRICT, related_name="venues")
    publicly_listed = models.BooleanField(default=True)

    slug = AutoSlugField(populate_from="name", unique=True, blank=True)

    def get_productions(self):
        """The productions in this Venue

        Returns:
            list of Production: A list of all the productions in this Venue.
        """
        production_model = apps.get_model("productions", "production")
        return production_model.objects.filter(performances__venue=self).distinct()

    def __str__(self):
        return str(self.name)

    class Meta:
        ordering = ["id"]


class SeatGroup(BaseModel):
    """The model for a region of a Venue.

    A seat group is a region of a Venue, it can contains many seats or
    just be a generic area. eg front row or standing section.

    In order to book a SeatGroup for a performance, a PerformanceSeatGroup must
    be created.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    venue = models.ForeignKey(
        Venue, on_delete=models.CASCADE, related_name="seat_groups"
    )
    capacity = models.IntegerField(null=True)
    seats = models.ForeignKey(Seat, on_delete=models.RESTRICT, null=True, blank=True)
    is_internal = models.BooleanField(default=True)

    def __str__(self):
        return str(self.name or self.id)

    class Meta:
        ordering = ["id"]
