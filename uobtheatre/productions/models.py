import datetime
import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from autoslug import AutoSlugField
from django.db import models
from django.db.models import Max, Min, Sum
from django.db.models.query import QuerySet
from django.utils import timezone

from uobtheatre.images.models import Image
from uobtheatre.societies.models import Society
from uobtheatre.utils.models import TimeStampedMixin
from uobtheatre.venues.models import SeatGroup, Venue

if TYPE_CHECKING:
    from uobtheatre.bookings.models import Ticket, ConcessionType


class CrewRole(models.Model):
    """A CrewMember's role in a production."""

    class Department(models.TextChoices):
        """The department which the CrewRole is in."""

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
        return str(self.name)


class AudienceWarning(models.Model):
    """A warning about a Production.

    In many cases Productions have speciifc warnings which they wish to inform
    the audience about before they purchase tickets.
    """

    description = models.CharField(max_length=255)

    def __str__(self):
        return str(self.description)


def append_production_qs(queryset, start=False, end=False):
    """Given a booking queryset append extra fields.

    The additional field which can be added are:
        - start
        - end

    Args:
        queryset (Queryset): The production queryset.
        start (bool): Whether the start field should be annotated.
            (default is False)
        end (bool): Whether the end field should be annotated.
            (default is False)

    Returns:
        Queryset: The Queryset with the additional fields annotated.
    """
    if start:
        queryset = queryset.annotate(start=Min("performances__start"))
    if end:
        queryset = queryset.annotate(end=Max("performances__end"))
    return queryset


class Production(TimeStampedMixin, models.Model):
    """The model for a production.

    A production is a show (like the 2 weeks things) and can have many
    performaces (these are like the nights).
    """

    name = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, null=True)
    description = models.TextField(null=True)

    society = models.ForeignKey(
        Society, on_delete=models.SET_NULL, null=True, related_name="productions"
    )

    cover_image = models.ForeignKey(
        Image,
        on_delete=models.RESTRICT,
        related_name="production_cover_images",
        null=True,
        blank=True,
    )
    poster_image = models.ForeignKey(
        Image,
        on_delete=models.RESTRICT,
        related_name="production_poster_images",
        null=True,
        blank=True,
    )
    featured_image = models.ForeignKey(
        Image,
        on_delete=models.RESTRICT,
        related_name="production_featured_images",
        null=True,
        blank=True,
    )

    age_rating = models.SmallIntegerField(null=True)
    facebook_event = models.CharField(max_length=255, null=True)

    warnings = models.ManyToManyField(AudienceWarning, blank=True)

    slug = AutoSlugField(populate_from="name", unique=True, blank=True)

    def __str__(self):
        return str(self.name)

    def is_upcoming(self) -> bool:
        """If the show has performances in the future.

        A show is upcoming if it has a performance that has not ended.

        Returns:
            bool: If the proudction is upcoming
        """
        return self.performances.filter(start__gte=timezone.now()).count() != 0

    def is_bookable(self) -> bool:
        """If this Production can be booked.

        Returns if the show is bookable, based on if it has enabled
        performances.

        Returns:
            bool: If the booking can be booked.
        """
        return self.performances.filter(disabled=False).count() != 0

    def end_date(self):
        """When the last Performance of the Production ends.

        Returns:
            datetime: The end datatime of the Production.
        """
        return self.performances.all().aggregate(Max("end"))["end__max"]

    def start_date(self):
        """When the first performance starts.

        Returns:
            datetime: The start datatime of the Production.
        """
        return self.performances.all().aggregate(Min("start"))["start__min"]

    def min_seat_price(self) -> Optional[int]:
        """The price of the cheapest seat available for this production.

        Return the minimum seatgroup ticket price for each performance. This is
        used to say "Tickets from £x".

        Returns:
            int, optional: The price of the cheapest seat in pennies. If no
                SeatGroups are added to this Booking then None is returned.
        """
        performances = self.performances.all()
        all_min_seat_prices = [
            performance.min_seat_price() for performance in performances
        ]

        return min(
            (
                min_seat_prices
                for min_seat_prices in all_min_seat_prices
                if min_seat_prices is not None
            ),
            default=None,
        )

    def duration(self) -> Optional[datetime.timedelta]:
        """The duration of the shortest show as a datetime object.

        Returns:
            datetime: The duration of the shortest production.
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
    profile_picture = models.ForeignKey(
        Image,
        on_delete=models.RESTRICT,
        related_name="cast_members",
        blank=True,
        null=True,
    )
    role = models.CharField(max_length=255, null=True)
    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="cast"
    )

    def __str__(self):
        return str(self.name)

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
        return str(self.name)

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
        return str(self.name)

    class Meta:
        ordering = ["id"]


class Performance(TimeStampedMixin, models.Model):
    """The model for a Performance of a Production.

    A performance is a discrete event when the show takes place eg 7pm on
    Tuesday.
    """

    production = models.ForeignKey(
        Production,
        on_delete=models.CASCADE,
        related_name="performances",
    )

    venue = models.ForeignKey(
        Venue,
        on_delete=models.SET_NULL,
        null=True,
        related_name="performances",
    )

    doors_open = models.DateTimeField(null=True)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)

    description = models.TextField(null=True, blank=True)
    extra_information = models.TextField(null=True, blank=True)

    disabled = models.BooleanField(default=True)

    seat_groups = models.ManyToManyField(SeatGroup, through="PerformanceSeatGroup")

    capacity = models.IntegerField(null=True, blank=True)

    def tickets(self, seat_group=None) -> List["Ticket"]:
        """Get tickets for this performance

        Args:
            seat_group (SeatGroup): A SeatGroup to filter the tickets by. If a
                SeatGroup is supplied only tickets for that SeatGroup will be
                returned.
                (default None)

        Returns:
            list of Tickets: The Ticket in the Booking. If SeatGroup supplied
                then only the Tickets in that SeatGroup.
        """
        filters = {}
        if seat_group:
            filters["seat_group"] = seat_group

        return [
            ticket
            for booking in self.bookings.all()
            for ticket in booking.tickets.filter(**filters)
        ]

    def total_capacity(self, seat_group=None):
        """Total capacity of the Performance.

        The is the total number of seats (Tickets) which can be booked for this
        performance. This does not take into account any existing Bookings.

        Note:
            The sum of the capacities of all the seat groups is not necessarily
            equal to that of the Performance (the performance may be less).

        Args:
            seat_group (SeatGroup): If supplied the capacity of that SeatGroup is returned.
                (default None)

        Returns:
            int: The capacity of the show (or SeatGroup if provided)
        """
        if seat_group:
            queryset = self.performance_seat_groups
            try:
                return queryset.get(seat_group=seat_group).capacity
            except queryset.model.DoesNotExist:
                return 0
        response = self.performance_seat_groups.aggregate(Sum("capacity"))
        return response["capacity__sum"] or 0

    def capacity_remaining(self, seat_group: SeatGroup = None):
        """Remaining capacity of the Performance.

        The is the total number of seats (Tickets) which can be booked for this
        performance when factoring in existing Bookings.

        Note:
            The sum of the remaining capacities of all the seat groups is not
            necessarily equal to that of the Performance (the performance may
            be less).

        Args:
            seat_group (SeatGroup): If supplied the remaining capacity of that
                SeatGroup is returned.
                (default None)

        Returns:
            int: The remaining capacity of the show (or SeatGroup if provided)
        """
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
        """The performances duration.

        Duration is measured from start time to end time.

        Returns:
            datetime: Performance duration.
        """
        return self.end - self.start

    def get_single_discounts(self) -> QuerySet[Any]:
        """QuerySet for single discounts available for this Performance.

        Returns:
            QuerySet: This performances discount QuerySet filter to only
                return single discounts.
        """
        return self.discounts.annotate(
            number_of_tickets_required=Sum("requirements__number")
        ).filter(number_of_tickets_required=1)

    def get_concession_discount(self, concession_type) -> float:
        """Discount value for a concession type.

        Given a concession type find the single discount which applies to that
        ConcessionType, if there is one. If there is return the percentage of
        the discount. If no single discount for that concession type is found
        return 0.

        Args:
            (ConcessionType): The concession type for the discount.

        Returns:
            int: The value of the single discount on the concession type.
        """
        discount = next(
            (
                discount
                for discount in self.get_single_discounts()
                if discount.requirements.first().concession_type == concession_type
            ),
            None,
        )
        return discount.percentage if discount else 0

    def price_with_concession(
        self,
        concession: "ConcessionType",
        performance_seat_group: "PerformanceSeatGroup",
    ) -> int:
        """Price with single concession applied.

        Given a concession type and a price, returns the new price once the
        concession discount is applied.

        Args:
            (ConcessionType): The concession type for the discount.
            (PerformanceSeatGroup): The PerformanceSeatGroup which is being
                discounted.

        Returns:
            int: price in pennies once concession discount applied.
        """
        price = performance_seat_group.price if performance_seat_group else 0
        return math.ceil((1 - self.get_concession_discount(concession)) * price)

    def concessions(self) -> List:
        """Available concession types for this Performance.

        Concession are only available to a Performance if they are in a related
        discount. This returns all the Performance's available Concessions

        Returns:
            list of ConcessionType: The concessions available for this
                performance.
        """

        concession_list = list(
            set(
                discounts_requirement.concession_type
                for discount in self.discounts.all()
                for discounts_requirement in discount.requirements.all()
            )
        )
        concession_list.sort(key=lambda concession: concession.id)
        return concession_list

    def min_seat_price(self) -> Optional[int]:
        """The cheapest seat in the Performance

        Returns:
            int: The price of the cheapest seat in the performance.
        """
        return self.performance_seat_groups.aggregate(Min("price"))["price__min"]

    def is_sold_out(self) -> bool:
        """If the performance is sold out

        Returns:
            bool: if the performance is soldout.
        """
        return self.capacity_remaining() == 0

    def check_capacity(self, tickets, deleted_tickets=None) -> Optional[str]:
        """Check the capacity with ticket changes.

        Used to check if an update to the Performances Tickets is possible with
        the Performance's (and its SeatGroups) capacity.

        Given a list of ticket objects to create and a list of ticket object to
        delete, check if there are enough tickets available for the booking. If
        not return a string error.

        Args:
            tickets (list of Tickets): The list of tickets which are to be
                created.
            deleted_tickets (list of Tickets): The list of tickets which are to
                be deleted.
                (default: [])

        Returns:
            str, Optional: The reason why the new capacity (after ticket
                update) is not valid. If update is valid None is returned.
        """

        if deleted_tickets is None:
            deleted_tickets = []

        # TODO return a custom exception not a string

        # Get the number of each seat group
        seat_group_counts: Dict[SeatGroup, int] = {}
        for ticket in tickets:
            # If a SeatGroup with this id does not exist an error will the thrown
            seat_group = ticket.seat_group
            seat_group_count = seat_group_counts.get(seat_group)
            seat_group_counts[seat_group] = (seat_group_count or 0) + 1

        # Then reduce the count if tickets are being deleted. This is because
        # if we have booked a seat in the front row, and we then decide to
        # delete that seat and book a new one in the same row we only need 1
        # seat (i.e no more seats)
        for ticket in deleted_tickets:
            # If a SeatGroup with this id does not exist an error will the thrown
            seat_group = ticket.seat_group
            seat_group_count = seat_group_counts.get(seat_group)
            seat_group_counts[seat_group] = (seat_group_count or 0) - 1

        # Check each seat group is in the performance
        seat_groups_not_in_perfromance: List[str] = [
            seat_group.name
            for seat_group in seat_group_counts.keys()  # pylint: disable=consider-iterating-dictionary
            if seat_group not in self.seat_groups.all()
        ]

        # If any of the seat_groups are not assigned to this performance then throw an error
        if len(seat_groups_not_in_perfromance) != 0:
            seat_groups_not_in_perfromance_str = ", ".join(
                seat_groups_not_in_perfromance
            )
            performance_seat_groups_str = ", ".join(
                [seat_group.name for seat_group in self.seat_groups.all()]
            )
            return f"You cannot book a seat group that is not assigned to this performance, you have booked {seat_groups_not_in_perfromance_str} but the performance only has {performance_seat_groups_str}"

        # Check that each seat group has enough capacity
        for seat_group, number_booked in seat_group_counts.items():
            seat_group_remaining_capacity = self.capacity_remaining(
                seat_group=seat_group
            )
            if seat_group_remaining_capacity < number_booked:
                return f"There are only {seat_group_remaining_capacity} seats reamining in {seat_group} but you have booked {number_booked}. Please updated your seat selections and try again."

        # Also check total capacity
        if self.capacity_remaining() < len(tickets) - len(deleted_tickets):
            return f"There are only {self.capacity_remaining()} seats available for this performance. You attempted to book {len(tickets)}. Please remove some tickets and try again or select a different performance."

        return None

    def __str__(self):
        if self.start is None:
            return f"Perforamce of {self.production.name}"
        return f"Perforamce of {self.production.name} at {self.start.strftime('%H:%M')} on {self.start.strftime('%d/%m/%Y')}"

    class Meta:
        ordering = ["id"]


class PerformanceSeatGroup(models.Model):
    """Pivot table for Performace SeatGroup relation.

    To allow a SeatGroup to be booked for a Performance a PerformanceSeatGroup
    must be created. This provides the base price of the SeatGroup (without any
    discounts) and the capacity, the number of seats which can be booked in
    this SeatGroup.

    Note:
        The total of all the PerformanceSeatGroup's capacities can be greater
        than the Performance capacity. This is handled in the Performance
        get_capacity and remaining_capacity methods.
    """

    # TODO the capacity should default to the SeatGroup capacity.
    seat_group = models.ForeignKey(SeatGroup, on_delete=models.RESTRICT)
    performance = models.ForeignKey(
        Performance, on_delete=models.RESTRICT, related_name="performance_seat_groups"
    )
    price = models.IntegerField()
    capacity = models.SmallIntegerField(blank=True)
