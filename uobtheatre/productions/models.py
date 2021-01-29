import datetime
import math
from typing import List, Optional

from autoslug import AutoSlugField
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from uobtheatre.societies.models import Society
from uobtheatre.utils.models import TimeStampedMixin
from uobtheatre.venues.models import SeatGroup, Venue


class CrewRole(models.Model):
    """Crew role"""

    class Department(models.TextChoices):
        LX = "lighting", "Lighting"
        SND = "sound", "Sound"
        AV = "av", "AV"
        SM = "stage_management", "Stage Management"
        PYRO = "pryo", "Pyrotechnics"
        SET = "set", "Set"
        MISC = "misc", "Miscellaneous"

    name = models.CharField(max_length=255)
    department = models.CharField(
        max_length=20,
        choices=Department.choices,
        default=Department.MISC,
    )

    def __str__(self):
        return self.name


class Warning(models.Model):
    """A venue is a space often where shows take place"""

    warning = models.CharField(max_length=255)

    def __str__(self):
        return self.warning


class Production(models.Model, TimeStampedMixin):
    """A production is a show (like the 2 weeks things) and can have many
    performaces (these are like the nights).
    """

    name = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, null=True)
    description = models.TextField(null=True)

    society = models.ForeignKey(
        Society, on_delete=models.SET_NULL, null=True, related_name="productions"
    )

    poster_image = models.ImageField(null=True)
    featured_image = models.ImageField(null=True)
    cover_image = models.ImageField(null=True)

    age_rating = models.SmallIntegerField(null=True)
    facebook_event = models.CharField(max_length=255, null=True)

    warnings = models.ManyToManyField(Warning)

    slug = AutoSlugField(populate_from="name", unique=True, blank=True)

    def __str__(self):
        return self.name

    def is_upcoming(self) -> bool:
        """
        Returns if the show is upcoming. If the show has no upcoming
        productions (not ended) then it is not upcoming.
        """
        performances = self.performances.all()
        return any(
            performance.start > timezone.now()
            for performance in performances
            if performance.start
        )

    def end_date(self):
        """
        Return when the last performance ends.
        """
        performances = self.performances.all()
        if not performances:
            return None
        return max(performance.end for performance in performances)

    def start_date(self):
        """
        Return when the first performance starts.
        """
        performances = self.performances.all()
        if not performances:
            return None
        return min(performance.start for performance in performances)

    def duration(self) -> Optional[datetime.timedelta]:
        """
        Returns the duration of the shortest show as a datetime object.
        """
        performances = self.performances.all()
        if not performances:
            return None
        return min(performance.duration() for performance in performances)

    class Meta:
        ordering = ["id"]


class CastMember(models.Model):
    """Member of production cast"""

    name = models.CharField(max_length=255)
    profile_picture = models.ImageField(null=True, blank=True)
    role = models.CharField(max_length=255, null=True)
    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="cast"
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["id"]


class ProductionTeamMember(models.Model):
    """Member of production prod team"""

    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, null=True)
    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="production_team"
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["id"]


class CrewMember(models.Model):
    """Member of production crew"""

    name = models.CharField(max_length=255)
    role = models.ForeignKey(
        CrewRole, null=True, on_delete=models.SET_NULL, related_name="crew_members"
    )
    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="crew"
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["id"]


class Performance(models.Model, TimeStampedMixin):
    """
    A performance is a discrete event when the show takes place eg 7pm on
    Tuesday.
    """

    production = models.ForeignKey(
        Production,
        on_delete=models.CASCADE,
        related_name="performances",
    )

    venue = models.ForeignKey(
        Venue, on_delete=models.SET_NULL, null=True, related_name="performances"
    )

    doors_open = models.DateTimeField(null=True)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)

    description = models.TextField(null=True, blank=True)
    extra_information = models.TextField(null=True, blank=True)

    disabled = models.BooleanField(default=True)

    seat_groups = models.ManyToManyField(SeatGroup, through="PerformanceSeatGroup")

    capacity = models.IntegerField(null=True, blank=True)

    def tickets(self, seat_group=None):
        """ Get all tickets for this performance """
        filters = {}
        if seat_group:
            filters["seat_group"] = seat_group

        return [
            ticket
            for booking in self.bookings.all()
            for ticket in booking.tickets.filter(**filters)
        ]

    def total_capacity(self, seat_group=None):
        """ Returns the total capacity of show. """
        if seat_group:
            queryset = self.performance_seat_groups
            try:
                return queryset.get(seat_group=seat_group).capacity
            except queryset.model.DoesNotExist:
                return 0
        response = self.performance_seat_groups.aggregate(Sum("capacity"))
        return response["capacity__sum"] or 0

    def capacity_remaining(self, seat_group: SeatGroup = None):
        """ Returns the capacity remaining.  """
        if seat_group:
            return self.total_capacity(seat_group=seat_group) - len(
                self.tickets(seat_group=seat_group)
            )

        seat_groups_remaining_capacity = sum(
            self.capacity_remaining(seat_group=performance_seat_group.seat_group)
            for performance_seat_group in self.performance_seat_groups.all()
        )
        return (
            seat_groups_remaining_capacity
            if not self.capacity
            else min(
                self.capacity - len(self.tickets()), seat_groups_remaining_capacity
            )
        )

    def duration(self):
        """
        Returns the duration of the show as a datetime object
        """
        return self.end - self.start

    def get_single_discounts(self) -> List:
        """ Returns all discounts that apply to a single ticket """
        return [
            discount
            for discount in self.discounts.all()
            if discount.is_single_discount()
        ]

    def get_concession_discount(self, concession_type) -> float:
        """
        Given a seat_group and a concession type returns the concession type
        discount for the ticket.
        """
        discount = next(
            (
                discount
                for discount in self.get_single_discounts()
                if discount.discount_requirements.first().concession_type
                == concession_type
            ),
            None,
        )
        return discount.discount if discount else 0

    def price_with_concession(self, concession, price) -> int:
        """
        Given a seat_group and a concession type returns the price of the
        ticket with the single discounts applied.
        """
        return math.ceil((1 - self.get_concession_discount(concession)) * price)

    def concessions(self) -> List:
        """ Returns list of all concession types """
        concession_list = list(
            set(
                discounts_requirement.concession_type
                for discount in self.discounts.all()
                for discounts_requirement in discount.discount_requirements.all()
            )
        )
        concession_list.sort(key=lambda concession: concession.id)
        return concession_list

    def min_seat_price(self) -> Optional[int]:
        """
        Returns the price of the cheapest seat price
        """
        return min(
            (psg.price for psg in self.performance_seat_groups.all()), default=None
        )

    def check_capacity(self, tickets):
        """
        Given a list of ticket objects, checks there are enough tickets
        available for the booking. If not return a string.
        TODO return a custom exception not a string
        """

        # Get the number of each seat group
        seat_group_counts = {}
        for ticket in tickets:
            # If a SeatGroup with this id does not exist an error will the thrown
            seat_group = ticket.seat_group
            seat_group_count = seat_group_counts.get(seat_group)
            seat_group_counts[seat_group] = (seat_group_count or 0) + 1

        # Check each seat group is in the performance
        seat_groups_not_in_perfromance = [
            seat_group.name
            for seat_group in seat_group_counts.keys()
            if seat_group not in self.seat_groups.all()
        ]

        # If any of the seat_groups are not assigned to this performance then throw an error
        if len(seat_groups_not_in_perfromance) != 0:
            return f"You cannot book a seat group that is not assigned to this performance, you have booked {', '.join(seat_groups_not_in_perfromance)} but the performance only has {', '.join([seat_group.name for seat_group in self.seat_groups.all()])}"

        # Check that each seat group has enough capacity
        for seat_group, number_booked in seat_group_counts.items():
            seat_group_remaining_capacity = self.capacity_remaining(
                seat_group=seat_group
            )
            if seat_group_remaining_capacity < number_booked:
                return f"There are only {seat_group_remaining_capacity} seats reamining in {seat_group} but you have booked {number_booked}. Please updated your seat selections and try again."

        # Also check total capacity
        if self.capacity_remaining() < len(tickets):
            return f"There are only {self.capacity_remaining()} seats available for this performance. You attempted to book {len(tickets)}. Please remove some tickets and try again or select a different performance."

    def __str__(self):
        if self.start is None:
            return f"Perforamce of {self.production.name}"
        return f"Perforamce of {self.production.name} at {self.start.strftime('%H:%M')} on {self.start.strftime('%d/%m/%Y')}"

    class Meta:
        ordering = ["id"]


class PerformanceSeatGroup(models.Model):
    """ Storing the price and number of seats of each seat group for a show """

    seat_group = models.ForeignKey(SeatGroup, on_delete=models.RESTRICT)
    performance = models.ForeignKey(
        Performance, on_delete=models.RESTRICT, related_name="performance_seat_groups"
    )
    price = models.IntegerField()
    capacity = models.SmallIntegerField(blank=True)
