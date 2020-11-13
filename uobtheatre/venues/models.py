from django.db import models
from uobtheatre.utils.models import (
    SoftDeletionMixin,
    TimeStampedMixin,
)


class Venue(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A venue is a space often where shows take place"""

    name = models.CharField(max_length=255)
    internal_capacity = models.SmallIntegerField()

    def __str__(self):
        return self.name


class SeatType(models.Model):
    """The type of seat being purchased. This could descibe the type of seat eg
    front row, A1 or could descibe the location eg online,"""

    name = models.CharField(max_length=255)
    is_internal = models.BooleanField(default=True)


class SeatGroup(models.Model):
    seat_type = models.ForeignKey(SeatType, on_delete=models.SET_NULL)
    venue = models.ForeignKey(
        Venue, on_delete=models.CASCADE, related_name="seat_groups"
    )
    seat_row = models.CharField(max_length=5, null=True, blank=True)
    seat_number = models.CharField(null=True, blank=True)
    capacity = models.IntegerField(null=True)
