"""
Models for venues.
"""

from autoslug import AutoSlugField
from django.db import models

from uobtheatre.addresses.models import Address
from uobtheatre.images.models import Image
from uobtheatre.utils.models import TimeStampedMixin


class Seat(models.Model):
    """The model for a seat

    A seat is a single spot in a Venue which only one User can book per
    performance. In most cases this is literally a seat.
    """

    row = models.CharField(max_length=5, null=True, blank=True)
    number = models.CharField(max_length=5, null=True, blank=True)


class Venue(TimeStampedMixin, models.Model):
    """The model for a venue

    A Venue is a place where Performances can take place.
    """

    name = models.CharField(max_length=255)
    internal_capacity = models.SmallIntegerField()
    description = models.TextField(null=True)
    address = models.ForeignKey(Address, on_delete=models.CASCADE, null=True)
    image = models.ForeignKey(Image, on_delete=models.RESTRICT, related_name="venues")
    publicly_listed = models.BooleanField(default=True)

    slug = AutoSlugField(populate_from="name", unique=True, blank=True)

    def get_productions(self):
        """The productions in this Venue

        Returns:
            (list of Production): A list of all the productions in this Venue.
        """
        # TODO This should be a single query
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
        return self.name or str(self.id)

    class Meta:
        ordering = ["id"]
