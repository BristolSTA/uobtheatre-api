"""
Models for venues.
"""

from autoslug import AutoSlugField
from django.db import models

from uobtheatre.addresses.models import Address
from uobtheatre.images.models import Image
from uobtheatre.utils.models import TimeStampedMixin


class Seat(models.Model):
    """ A seat which can be booked """

    row = models.CharField(max_length=5, null=True, blank=True)
    number = models.CharField(max_length=5, null=True, blank=True)


class Venue(TimeStampedMixin, models.Model):
    """A venue is a space often where shows take place"""

    name = models.CharField(max_length=255)
    internal_capacity = models.SmallIntegerField()
    description = models.TextField(null=True)
    address = models.ForeignKey(Address, on_delete=models.CASCADE, null=True)
    image = models.ForeignKey(Image, on_delete=models.RESTRICT, related_name="venues")
    publicly_listed = models.BooleanField(default=True)

    slug = AutoSlugField(populate_from="name", unique=True, blank=True)

    def get_productions(self):
        productions = list(
            set(performance.production for performance in self.performances.all())
        )
        productions.sort(key=lambda prod: prod.id)
        return productions

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["id"]


class SeatGroup(models.Model):
    """A seat group is a collection of seats, it can contains many seats or
    just be a generic area eg front row or stading section"""

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    venue = models.ForeignKey(
        Venue, on_delete=models.CASCADE, related_name="seat_groups"
    )
    capacity = models.IntegerField(null=True)
    seats = models.ForeignKey(Seat, on_delete=models.RESTRICT, null=True, blank=True)
    is_internal = models.BooleanField(default=True)

    def __str__(self):
        return self.name or str(self.id)

    class Meta:
        ordering = ["id"]
