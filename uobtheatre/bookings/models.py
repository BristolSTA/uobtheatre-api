import uuid
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from rest_framework.authtoken.models import Token

from uobtheatre.productions.models import Perforamce
from uobtheatre.utils.models import (
    SoftDeletionMixin,
    TimeStampedMixin,
)
from uobtheatre.users.models import User


class TicketType(models.Model, SoftDeletionMixin):
    """
    Different pricing models for tickets eg Student/Family ticket.  When a
    ticket has mutliple people associated with it, it will store the number of
    people as well.
    """

    name = models.CharField(max_length=63)
    description = models.TextField()
    price = models.IntegerField()
    performance = models.ForeignKey(
        Perforamce, on_delete=models.CASCADE, related_name="ticket_price_bands"
    )
    number_of_people = models.SmallIntegerField(default=1)
    discount = models.SmallIntegerField(default=0)

    def __str__(self):
        return self.name


class SeatType(models.Model, SoftDeletionMixin):
    """Different types of seats for viewing the show eg Seated, standing,
    online or special seating bands such as front row"""

    name = models.CharField(max_length=63)
    description = models.TextField()
    price = models.IntegerField()
    performance = models.ForeignKey(
        Perforamce, on_delete=models.CASCADE, related_name="ticket_price_bands"
    )
    capacity = model.SmallIntegerField()
    number_of_people = models.SmallIntegerField(default=1)
    capacity = model.SmallIntegerField()

    def __str__(self):
        return self.name


class TicketType(models.Model, SoftDeletionMixin):
    """Different pricing models for tickets eg Student/Family ticket"""

    name = models.CharField(max_length=63)
    description = models.TextField()
    price = models.IntegerField()
    performance = models.ForeignKey(
        Perforamce, on_delete=models.CASCADE, related_name="ticket_price_bands"
    )
    capacity = model.SmallIntegerField()
    number_of_people = models.SmallIntegerField(default=1)

    def __str__(self):
        return self.name


class Booking(models.Model, TimeStampedMixin):
    """A booking is for one performance and has many tickets"""

    booking_reference = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="bookings")
    performance = models.ForeignKey(
        Perforamce, on_delete=models.CASCADE, related_name="performances"
    )

    def __str__(self):
        return self.booking_reference


class Ticket(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A ticket for a show, which often has a specific seat"""

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="tickets"
    )
    ticket_price_band = models.ForeignKey(TicketPriceBand, on_delete=models.SET_NULL)


class ConsessionType(models.Model):
    name = models.CharField(max_length=255)
