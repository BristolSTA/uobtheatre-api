from django.db import models

from uobtheatre.utils.models import SoftDeletionMixin, TimeStampedMixin


class Seat(models.Model):
    """ A seat which can be booked """

    row = models.CharField(max_length=5, null=True, blank=True)
    number = models.CharField(max_length=5, null=True, blank=True)


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

    def __str__(self):
        return self.name


class SeatGroup(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    seat_type = models.ForeignKey(SeatType, on_delete=models.SET_NULL, null=True)
    venue = models.ForeignKey(
        Venue, on_delete=models.CASCADE, related_name="seat_groups"
    )
    capacity = models.IntegerField(null=True)
    seat = models.ForeignKey(Seat, on_delete=models.RESTRICT, null=True, blank=True)
