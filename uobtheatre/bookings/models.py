import uuid
from django.db import models
from uobtheatre.productions.models import Performance
from uobtheatre.utils.models import (
    SoftDeletionMixin,
    TimeStampedMixin,
)
from uobtheatre.users.models import User
from uobtheatre.venues.models import SeatGroup


class ConsessionType(models.Model):
    name = models.CharField(max_length=255)


class Booking(models.Model, TimeStampedMixin):
    """A booking is for one performance and has many tickets"""

    booking_reference = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")

    def __str__(self):
        return self.booking_reference


class SeatBooking(models.Model):
    """A booking of a single seat (from a seat group)"""

    seat_group = models.ForeignKey(
        User, on_delete=models.RESTRICT, related_name="seat_bookings"
    )
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="seats")
    consession_type = models.ForeignKey(
        ConsessionType,
        on_delete=models.SET_NULL,
        related_name="seat_bookings",
        null=True,
    )
    performance = models.ForeignKey(
        Performance,
        on_delete=models.RESTRICT,
        related_name="seat_bookings",
    )
