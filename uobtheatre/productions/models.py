# pylint: disable=too-many-public-methods,too-many-lines
import datetime
import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from autoslug import AutoSlugField
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Max, Min, Q, Sum
from django.db.models.query import QuerySet
from django.utils import timezone
from django.utils.functional import cached_property
from django_tiptap.fields import TipTapTextField
from guardian.shortcuts import get_objects_for_user

from uobtheatre.images.models import Image
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.productions.exceptions import (
    InvalidConcessionTypeException,
    InvalidSeatGroupException,
    NotEnoughCapacityException,
)
from uobtheatre.productions.tasks import refund_performance
from uobtheatre.societies.models import Society
from uobtheatre.users.abilities import AbilitiesMixin
from uobtheatre.users.models import User
from uobtheatre.utils.models import (
    BaseModel,
    PermissionableModel,
    TimeStampedMixin,
    classproperty,
)
from uobtheatre.utils.validators import (
    RelatedObjectsValidator,
    RequiredFieldsValidator,
    ValidationError,
    ValidationErrors,
)
from uobtheatre.venues.models import SeatGroup, Venue

if TYPE_CHECKING:
    from uobtheatre.bookings.models import ConcessionType, TicketQuerySet


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


class ContentWarning(models.Model):
    """A warning about a Production.

    In many cases Productions have speciifc warnings which they wish to inform
    the audience about before they purchase tickets.
    """

    short_description = models.CharField(max_length=255)
    long_description = models.TextField(null=True, blank=True)

    def __str__(self):
        return str(self.short_description)


class ProductionContentWarning(models.Model):
    """Intermediate model between productions and warnings"""

    production = models.ForeignKey(
        "productions.production",
        on_delete=models.CASCADE,
        related_name="warnings_pivot",
    )
    warning = models.ForeignKey(ContentWarning, on_delete=models.CASCADE)
    information = models.TextField(null=True)


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
        "productions.Production",
        on_delete=models.CASCADE,
        related_name="cast",
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
        "productions.Production",
        on_delete=models.CASCADE,
        related_name="production_team",
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
        "productions.Production",
        on_delete=models.CASCADE,
        related_name="crew",
    )

    def __str__(self):
        return str(self.name)

    class Meta:
        ordering = ["id"]


class PerformanceQuerySet(QuerySet):
    """Queryset for Performances, also used as manager."""

    def running_on(self, date: datetime.date):
        """Performances running on the provided date.

        This means the performance must either start or still be
        running on the day.

        Args:
            date: The date which performances must be running on.

        Returns:
            QuerySet: The filtered queryset
        """
        return self.filter(start__date__lte=date, end__date__gte=date)

    def where_can_view_tickets_and_bookings(self, user: "User"):
        """Filter performances where the user is allowed to view tickets and bookings"""
        productions_with_perm = get_objects_for_user(
            user,
            ["productions.boxoffice", "productions.view_bookings"],
            accept_global_perms=True,
            with_superuser=True,
            any_perm=True,
        )
        return self.filter(production__in=productions_with_perm)

    def has_boxoffice_permission(self, user: "User", has_permission=True):
        """Filter performances where user has boxoffice permission.

        Returns the performances which the provided user has permission to
        access the boxoffice.

        Args:
            user (User): The user which is used in the filter.
            has_permission (bool): Whether to filter those which the user has
                permission for, or does not have permission for.

        Returns:
            QuerySet: The filtered queryset
        """
        production_with_perm = get_objects_for_user(
            user, "productions.boxoffice", accept_global_perms=True, with_superuser=True
        )
        if has_permission:
            return self.filter(production__in=production_with_perm)
        return self.exclude(production__in=production_with_perm)

    def user_can_see(self, user: "User"):
        """Filter performances which the user can see

        Returns the performances which the provided user has permission to see.

        Args:
            user (User): The user which is used in the filter.

        Returns:
            QuerySet: The filtered queryset
        """
        productions_user_can_view = Production.objects.user_can_see(user)  # type: ignore
        return self.filter(production__in=productions_user_can_view)

    def bookings(self):
        """
        Returns a queryset of all of the bookings associated with this
        booking.
        """
        from uobtheatre.bookings.models import Booking

        return Booking.objects.filter(performance__in=self)

    def transactions(self) -> QuerySet[Transaction]:
        """
        Returns a queryset of all of the transactions associated with this
        performance.
        """
        from uobtheatre.bookings.models import Booking

        return Transaction.objects.filter(
            pay_object_id__in=self.bookings().values_list("id", flat=True),
            pay_object_type=ContentType.objects.get_for_model(Booking),
        )

    def booked_users(self):
        """
        Get all the users that have booked this performance.

        This excludes any bookings that have been refunded.
        """
        return User.objects.filter(
            bookings__in=self.bookings()
            .refunded(bool_val=False)
            .filter(status=Payable.Status.PAID)
        ).distinct()


PerformanceManager = models.Manager.from_queryset(PerformanceQuerySet)


class Performance(
    TimeStampedMixin, BaseModel
):  # pylint: disable=too-many-public-methods
    """The model for a Performance of a Production.

    A performance is a discrete event when the show takes place eg 7pm on
    Tuesday.
    """

    VALIDATOR = (
        RequiredFieldsValidator(
            [
                "production",
                "venue",
                "doors_open",
                "start",
                "end",
            ]
        )
        & RelatedObjectsValidator(attribute="seat_groups", min_number=1)
        & RelatedObjectsValidator(attribute="discounts", min_number=1)
    )

    objects = PerformanceManager()

    production = models.ForeignKey(
        "productions.Production",
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
    interval_duration_mins = models.IntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(120)]
    )

    description = models.TextField(null=True, blank=True)
    extra_information = models.TextField(null=True, blank=True)

    disabled = models.BooleanField(default=True)

    seat_groups: models.ManyToManyField = models.ManyToManyField(
        SeatGroup, through="PerformanceSeatGroup"
    )

    capacity = models.IntegerField(null=True, blank=True)

    def validate(self):
        return self.VALIDATOR.validate(self)

    @property
    def tickets(self) -> "TicketQuerySet":
        """Get tickets for this performance

        Returns:
            list of Tickets: The Ticket in the Booking.
        """
        from uobtheatre.bookings.models import Ticket

        return Ticket.objects.filter(booking__in=self.bookings.all())  # type: ignore

    @property
    def checked_in_tickets(self) -> "TicketQuerySet":
        """Get all checked in tickets

        Returns:
            queryset(Tickets): all tickets for this performance which have been checked in.
        """
        return self.tickets.sold().filter(checked_in_at__isnull=False)  # type: ignore

    @property
    def unchecked_in_tickets(self) -> "TicketQuerySet":
        """Get all unchecked in tickets

        Returns:
            queryset(Tickets): all tickets for this performance which have not been checked in.
        """
        return self.tickets.sold().filter(checked_in_at__isnull=True)  # type: ignore

    @property
    def has_group_discounts(self) -> bool:
        """
        Returns true if any of the discounts for this production have more than
        1 ticket in the requirements.

        Returns:
            bool: Whether the peformance has group discounts available.
        """
        return (
            self.discounts.annotate(
                number_of_tickets_required=Sum("requirements__number")
            )
            .filter(number_of_tickets_required__gt=1)
            .exists()
        )

    def total_seat_group_capacity(self, seat_group=None):
        """The sum of the capacities of all the seat groups in this performance.

        Note:
            The sum of the capacities of all the seat groups is not necessarily
            equal to that of the Performance (the performance may be less).

        Args:
            seat_group (SeatGroup): If supplied the capacity of that SeatGroup is returned.
                (default None)

        Returns:
            int: The capacity of the seat groups (or SeatGroup if provided) of the show
        """
        if seat_group:
            queryset = self.performance_seat_groups
            try:
                return queryset.get(seat_group=seat_group).capacity
            except queryset.model.DoesNotExist:
                return 0
        response = self.performance_seat_groups.aggregate(Sum("capacity"))
        return response["capacity__sum"] or 0

    def seat_group_capacity_remaining(self, seat_group: SeatGroup):
        """Get the number of available tickets able to be sold on a seat group"""
        return min(
            self.total_capacity
            - self.total_tickets_sold_or_reserved(),  # Top-level performance capacity remaining
            self.total_seat_group_capacity(seat_group=seat_group)
            - self.total_tickets_sold_or_reserved(
                seat_group=seat_group
            ),  # The capacity remaining for the local seat group capacity
        )

    @property
    def capacity_remaining(self):
        """Remaining capacity of the Performance.

        The is the total number of seats (Tickets) which can be booked for this
        performance when factoring in existing Bookings.

        Note:
            The sum of the remaining capacities of all the seat groups is not
            necessarily equal to that of the Performance (the performance may
            be less).

        Returns:
            int: The remaining capacity of the show (or SeatGroup if provided)
        """
        seat_groups_remaining_capacity = sum(
            self.seat_group_capacity_remaining(performance_seat_group.seat_group)
            for performance_seat_group in self.performance_seat_groups.all()
        )

        # The number of tickets remaining is the number of tickets left in the seat groups or the total capacity left for the performance - which ever is lower
        return min(
            seat_groups_remaining_capacity,
            self.total_capacity - self.total_tickets_sold_or_reserved(),
        )

    @property
    def total_capacity(self) -> int:
        """Total capacity of the Performance.

        The is the total number of seats (Tickets) which can be booked for this
        performance. This does not take into account any existing Bookings.

        Returns:
            int: The capacity of the show
        """

        limiting_capacities = [
            self.total_seat_group_capacity(),
        ]

        if self.venue:
            limiting_capacities.append(self.venue.internal_capacity)
        if self.capacity:
            limiting_capacities.append(self.capacity)

        return min(limiting_capacities)

    def total_tickets_sold(self, **kwargs):
        """The number of tickets sold for the performance

        Args:
            **kwargs (dict): Any additonal kwargs are used to filter the queryset.

        Returns:
            int: The number of tickets sold
        """
        return (
            self.tickets.sold()
            .filter(
                **kwargs,
            )
            .count()
        )

    def total_tickets_sold_or_reserved(self, **kwargs):
        """The number of tickets available for the performance (i.e. factoring in any draft bookings)

        Args:
            **kwargs (dict): Any additonal kwargs are used to filter the queryset.

        Returns:
            int: The number of tickets sold
        """
        return (
            self.tickets.sold_or_reserved()
            .filter(
                **kwargs,
            )
            .count()
        )

    @property
    def total_tickets_checked_in(self):
        """The number of tickets checked in for the performance

        Returns:
            int: The number of tickets
        """
        return self.checked_in_tickets.count()

    @property
    def total_tickets_unchecked_in(self):
        """The number of tickets not checked in for the performance

        Returns:
            int: The number of tickets
        """
        return self.unchecked_in_tickets.count()

    @property
    def duration(self) -> Optional[datetime.timedelta]:
        """The performances duration.

        Duration is measured from start time to end time.

        Returns:
            timedelta: Timedelta between start and end of performance.
        """
        if not self.start or not self.end:
            return None
        return self.end - self.start

    @cached_property
    def single_discounts_map(self) -> Dict["ConcessionType", float]:
        """Get the discount value for each concession type

        Returns:
            dict: Map of concession types to thier single discount percentage

        """
        return {
            discount.requirements.first().concession_type: discount.percentage
            for discount in self.get_single_discounts()
        }

    def get_single_discounts(self) -> QuerySet[Any]:
        """QuerySet for single discounts available for this Performance.

        Returns:
            QuerySet: This performances discount QuerySet filter to only
                return single discounts.
        """
        return self.discounts.annotate(
            number_of_tickets_required=Sum("requirements__number")
        ).filter(number_of_tickets_required=1)

    def price_with_concession(
        self,
        concession_type: "ConcessionType",
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
        return math.ceil(
            (1 - self.single_discounts_map.get(concession_type, 0)) * price
        )

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
            int: The price of the cheapest seat in the performance
            (includes discounted seat options).
        """
        max_discount_percentage = max(self.single_discounts_map.values(), default=0)

        if (
            min_seat_price := self.performance_seat_groups.aggregate(Min("price"))[
                "price__min"
            ]
        ) is not None:
            return math.ceil((1 - max_discount_percentage) * min_seat_price)
        return None

    @property
    def is_sold_out(self) -> bool:
        """If the performance is sold out

        Returns:
            bool: if the performance is soldout.
        """
        return self.capacity_remaining == 0

    @property
    def is_bookable(self) -> bool:
        return not (
            self.disabled
            or self.is_sold_out
            or (self.end and self.end < timezone.now())
        )

    def validate_tickets(self, tickets, deleted_tickets=None):
        """Validates a set of tickets to be added to the performance.

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

        Raises:
            InvalidSeatGroupException: A supplied ticket has a seat group that
                is not compatiable with the performance
            InvalidConcessionTypeException: A supplied ticket has a concession
                that is not compatiable with the performance
            NotEnoughCapacityException: The supplied tickets would cause a
                breach of available capacity
        """

        if deleted_tickets is None:
            deleted_tickets = []

        # Get the number of each seat group
        seat_group_counts: Dict[SeatGroup, int] = {}  # type: ignore
        for ticket in tickets:
            # If a SeatGroup with this id does not exist an error will be thrown
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
        seat_groups_not_in_performance: List[str] = [  # type: ignore
            seat_group.name
            for seat_group in seat_group_counts.keys()  # pylint: disable=consider-iterating-dictionary
            if seat_group not in self.seat_groups.all()
        ]

        # If any of the seat_groups are not assigned to this performance then throw an error
        if len(seat_groups_not_in_performance) != 0:
            seat_groups_not_in_performance_str = ", ".join(
                seat_groups_not_in_performance
            )
            performance_seat_groups_str = ", ".join(
                [seat_group.name for seat_group in self.seat_groups.all()]
            )
            raise InvalidSeatGroupException(
                f"You cannot book a seat group that is not assigned to this performance. You have booked {seat_groups_not_in_performance_str} but the performance only has {performance_seat_groups_str}"
            )

        # Check that each seat group has enough capacity
        for seat_group, number_booked in seat_group_counts.items():
            seat_group_remaining_capacity = self.seat_group_capacity_remaining(
                seat_group=seat_group
            )
            if seat_group_remaining_capacity < number_booked:
                raise NotEnoughCapacityException(
                    f"There are only {seat_group_remaining_capacity} seats reamining in {seat_group} but you have booked {number_booked}. Please updated your seat selections and try again."
                )

        # Check each concession type is in the performance
        concession_types = {ticket.concession_type for ticket in tickets}
        concession_types_not_in_performance: List[str] = [  # type: ignore
            concession_type.name
            for concession_type in concession_types  # pylint: disable=consider-iterating-dictionary
            if concession_type not in self.single_discounts_map.keys()
        ]

        if concession_types_not_in_performance:
            raise InvalidConcessionTypeException(
                f"{' '.join(concession_types_not_in_performance)} are not assigned to the performance {self}"
            )

    def has_boxoffice_permission(self, user: "User") -> bool:
        """
        Return whether the user has accesss to this performance's boxoffice

        Args:
            user (User): The user who is being checked

        Returns:
            bool: Whether the user has permission
        """
        if user.has_perm("productions.boxoffice", self.production):
            return True
        return False

    def sales_breakdown(self, breakdowns: Optional[list[str]] = None):
        """Generates a breakdown of the sales of this performance"""
        return self.qs.transactions().annotate_sales_breakdown(breakdowns)

    def refund_bookings(
        self,
        authorizing_user: User,
        preserve_provider_fees: bool = True,
        preserve_app_fees: bool = False,
    ):
        """Refund the performance's bookings

        Args:
            authorizing_user (User): The user authorizing the refund
            preserve_provider_fees (bool): If true the refund is reduced by the amount required to cover the payment's provider_fee
                i.e. the refund is reduced by the amount required to cover only Square's fees.
                If both preserve_provider_fees and preserve_app_fees are true, the refund is reduced by the larger of the two fees.
            preserve_app_fees (bool): If true the refund is reduced by the amount required to cover the payment's app_fee
                i.e. the refund is reduced by the amount required to cover our fees (the various misc_costs, such as the theatre improvement levy).
                If both preserve_provider_fees and preserve_app_fees are true, the refund is reduced by the larger of the two fees.

        Raises:
            CantBeRefundedException: Raised if the performance can't be refunded
        """
        if not self.disabled:
            raise CantBeRefundedException(f"{self} is not set to disabled")

        refund_performance.delay(
            self.pk, authorizing_user.id, preserve_provider_fees, preserve_app_fees
        )

    def __str__(self):
        if self.start is None:
            return f"Performance of {self.production.name}"
        return f"Performance of {self.production.name} at {self.start.strftime('%H:%M')} on {self.start.strftime('%d/%m/%Y')}"

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

    seat_group = models.ForeignKey(SeatGroup, on_delete=models.RESTRICT)
    performance = models.ForeignKey(
        Performance, on_delete=models.RESTRICT, related_name="performance_seat_groups"
    )
    price = models.PositiveIntegerField()
    capacity = models.PositiveSmallIntegerField(blank=True)

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.capacity is None:
                self.capacity = self.seat_group.capacity
        super().save(*args, **kwargs)


class ProductionQuerySet(QuerySet):
    """Queryset for Productions, also used as manager."""

    def annotate_start(self):
        """Annotate start datetime to queryset"""
        return self.annotate(start=Min("performances__start"))

    def annotate_end(self):
        """Annotate end datetime to queryset"""
        return self.annotate(end=Max("performances__end"))

    def user_can_see(self, user: "User"):
        """Filter productions which the user can see

        Returns the productions which the provided user has permission to see.

        Args:
            user (User): The user which is used in the filter.

        Returns:
            QuerySet: The filtered queryset
        """
        # Productions the user has explicit permissions to view
        productions_user_can_view_admin = get_objects_for_user(
            user, ["view_production", "approve_production"], self, any_perm=True
        ).values_list("id", flat=True)

        # Productions the user has tickets for that are within the last week or the future
        productions_user_has_tickets = []
        if user.is_authenticated:
            one_week_ago = timezone.now() - datetime.timedelta(days=7)
            productions_user_has_tickets = self.filter(
                performances__bookings__user=user,
                performances__start__gte=one_week_ago,
            ).values_list("id", flat=True)

        return self.filter(
            ~Q(status__in=Production.Status.PRIVATE_STATUSES)
            | Q(id__in=productions_user_can_view_admin)
            | Q(id__in=productions_user_has_tickets)
        )

    def performances(self):
        """
        Returns a queryset of all performances for the productions in the
        queryset.
        """
        return Performance.objects.filter(production__in=self)

    def transactions(self) -> QuerySet[Transaction]:
        """
        Returns a queryset of all of the transactions associated with this
        production.
        """
        return self.performances().transactions()


ProductionManager = models.Manager.from_queryset(ProductionQuerySet)


class Production(TimeStampedMixin, PermissionableModel, AbilitiesMixin, BaseModel):
    """The model for a production.

    A production is a show (like the 2 weeks things) and can have many
    performaces (these are like the nights).
    """

    objects = ProductionManager()
    from uobtheatre.productions.abilities import EditProduction

    abilities = [EditProduction]

    name = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, null=True, blank=True)

    description = TipTapTextField(null=True, blank=True)
    short_description = models.CharField(max_length=255, null=True, blank=True)

    venues = models.ManyToManyField(Venue, through=Performance, editable=False)

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

    VALIDATOR = RequiredFieldsValidator(
        [
            "name",
            "description",
            "society",
            "poster_image",
            "featured_image",
            "contact_email",
        ]
    ) & RelatedObjectsValidator(
        attribute="performances", validator=Performance.VALIDATOR, min_number=1
    )

    class Status(models.TextChoices):
        """The overall status of the production"""

        DRAFT = "DRAFT", "Draft"  # Production is in draft
        PENDING = "PENDING", "Pending"  # Produciton is pending publication/review
        APPROVED = (
            "APPROVED",
            "Approved",
        )  # Production has been aproved, but is not public
        PUBLISHED = (
            "PUBLISHED",
            "Published",
        )  # Production is public
        CLOSED = (
            "CLOSED",
            "Closed",
        )  # Production has been closed after it's run. No edits allowed.
        COMPLETE = (
            "COMPLETE",
            "Complete",
        )  # Production has been closed and paid for/transactions settled

        @classmethod
        @classproperty
        def PRIVATE_STATUSES(cls):  # pylint: disable=invalid-name
            return [cls.DRAFT, cls.PENDING, cls.APPROVED]

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )

    age_rating = models.SmallIntegerField(null=True, blank=True)
    facebook_event = models.CharField(max_length=255, null=True, blank=True)

    contact_email = models.EmailField(null=True, blank=True)

    content_warnings = models.ManyToManyField(
        ContentWarning, blank=True, through=ProductionContentWarning
    )

    production_alert = models.TextField(null=True, blank=True)

    slug = AutoSlugField(populate_from="name", unique=True, blank=True, editable=True)

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
        return any(performance.is_bookable for performance in self.performances.all())

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

    @property
    def duration(self) -> Optional[datetime.timedelta]:
        """The duration of the shortest show as a datetime object.

        Returns:
            datetime: The duration of the shortest production.
        """
        performances = self.performances.all()
        if not performances:
            return None
        return min(performance.duration for performance in performances)

    @property
    def total_capacity(self) -> int:
        """The total number of tickets which can be sold across all performances"""
        return sum(
            performance.total_capacity for performance in self.performances.all()
        )

    @property
    def total_tickets_sold(self) -> int:
        """The total number of tickets sold across all performances"""
        return sum(
            performance.total_tickets_sold() for performance in self.performances.all()
        )

    def sales_breakdown(self, breakdowns: Optional[list[str]] = None):
        """Generates a breakdown of the sales of this production"""
        return self.qs.transactions().annotate_sales_breakdown(breakdowns)

    def validate(self) -> Optional[ValidationErrors]:
        return self.VALIDATOR.validate(self)

    class Meta:
        ordering = ["id"]
        permissions = (
            ("boxoffice", "Can use box office for production"),
            ("sales", "Can view sales for production"),
            ("force_change_production", "Can change production once live"),
            ("view_bookings", "Can inspect bookings and users for this production"),
            ("approve_production", "Can approve production"),
            ("comp_tickets", "Can issue complimentary tickets"),
        )

    class PermissionsMeta:
        schema_assignable_permissions = {
            "boxoffice": ("change_production", "force_change_production"),
            "view_production": ("change_production", "force_change_production"),
            "view_bookings": ("change_production", "force_change_production"),
            "change_production": ("change_production", "force_change_production"),
            "sales": ("change_production", "force_change_production"),
            "comp_tickets": ("change_production", "force_change_production"),
            "approve_production": ("approve_production"),
        }
