import datetime
import math
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import urlencode

from django.contrib.postgres.aggregates import BoolAnd
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Case, F, FloatField, Q, Value, When
from django.db.models.functions import Cast
from django.db.models.query import QuerySet
from django.utils import timezone
from django.utils.functional import cached_property
from graphql_relay.node.node import to_global_id

import uobtheatre.bookings.emails as booking_emails
from uobtheatre.discounts.models import ConcessionType, DiscountCombination
from uobtheatre.payments.exceptions import (
    CantBePaidForException,
    CantBeRefundedException,
)
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable, PayableQuerySet
from uobtheatre.productions.models import Performance, Production
from uobtheatre.users.models import User
from uobtheatre.utils.exceptions import GQLException
from uobtheatre.utils.filters import filter_passes_on_model
from uobtheatre.utils.models import BaseModel, TimeStampedMixin
from uobtheatre.utils.utils import combinations, create_short_uuid
from uobtheatre.venues.models import Seat, SeatGroup

if TYPE_CHECKING:
    from uobtheatre.payments.transaction_providers import PaymentProvider


class MiscCostQuerySet(PayableQuerySet):
    """QuerySet for bookings"""

    def value(self, payable: "Payable") -> int:
        """Compute numerical value of selected misc costs on a given payable

        Args:
            payable (Payable): The payable to calculate the value of the misc
                costs on.

        Returns:
            int: The value of the misc costs in pence
        """
        return sum(misc_cost.get_value(payable) for misc_cost in self)


MiscCostManager = models.Manager.from_queryset(MiscCostQuerySet)


class MiscCost(models.Model):
    """Model for miscellaneous costs for shows

    Additional costs are added to a booking's final total.
    For example: Booking fee/Theatre improvement levy.

    A misc costs is defined by either a value or a percentage, but not both.

    Percentages are in decimal form (e.g. 0.1 for 10%).
    Value is in pence.

    Note:
        Currently all misc costs are applied to all bookings.
    """

    objects = MiscCostManager()
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    percentage = models.FloatField(
        null=True, blank=True, validators=[MaxValueValidator(1), MinValueValidator(0)]
    )
    value = models.FloatField(null=True, blank=True)

    def get_value(self, payable: "Payable") -> int:
        """Calculate the value of the misc cost on a booking.

        Calculate the value of the misc cost given a booking. The value is
        based on the subtotal of the Booking (the price of tickets with
        discounts applied).

        This will always return an value (not optional) as the model is
        required to either have a non null percentage or a non null value.

        This will return 0 if the booking is complimentary (subtotal = 0).

        Args:
            payable (Payable): The payable on which the misc cost is being
                applied.

        Returns:
            int: The value in pennies of the misc cost on this booking.
        """
        if self.percentage is not None:
            return math.ceil(payable.subtotal * self.percentage)

        if payable.subtotal == 0:
            return 0
        return self.value  # type: ignore

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="percentage_or_value_must_be_set_on_misc_cost",
                check=(
                    models.Q(
                        percentage__isnull=True,
                        value__isnull=False,
                    )
                    | models.Q(
                        percentage__isnull=False,
                        value__isnull=True,
                    )
                ),
            )
        ]


class BookingQuerySet(PayableQuerySet):
    """QuerySet for bookings"""

    def annotate_checked_in(self) -> QuerySet:
        return self.annotate(
            checked_in=BoolAnd(Q(tickets__checked_in_at__isnull=False))
        )

    def annotate_checked_in_count(self) -> QuerySet:
        return self.annotate(count=models.Count("tickets")).annotate(
            checked_in_count=models.Count(
                Case(When(tickets__checked_in_at__isnull=False, then=Value(1)))
            )
        )

    def annotate_checked_in_proportion(self) -> QuerySet:
        # To calculate the proportion of tickets that are checked in you need two values
        # the first - the number of tickets
        # the second - the number of tickets that are checked in
        # Whilst it shouldn't occur a divide by zero is prevented setting to zero when the ticket count is zero
        return self.annotate_checked_in_count().annotate(
            proportion=Case(
                When(Q(count=0), then=Cast(0, FloatField())),  # type: ignore
                default=Cast(F("checked_in_count"), FloatField())
                / Cast(F("count"), FloatField()),
            )
        )

    def checked_in(self, bool_val=True) -> QuerySet:
        """Bookings with checked in will be returned

        Args:
            bool_val (bool): when True: return only bookings with all tickets checked in,
            when False: return all bookings with atleast one ticket that is not checked in.

        Returns:
            QuerySet: the filtered queryset
        """

        if bool_val:
            query_set = self.annotate_checked_in().filter(checked_in=True)
        else:
            query_set = self.annotate_checked_in_count().filter(
                checked_in_count__lt=F("count")
            )
        return query_set

    def active(self, bool_val=True) -> QuerySet:
        """Bookings that are active (end time is in the future) will be returned

        Args:
            bool_val (bool): when True: return only active bookings,
            when False: return only old bookings (bookings for performances with end dates in the past)

        Returns:
            QuerySet: the filtered queryset
        """
        if bool_val:
            query_set = self.filter(performance__end__gte=timezone.now())
        else:
            query_set = self.filter(performance__end__lte=timezone.now())

        return query_set

    def expired(self, bool_val=True) -> QuerySet:
        """Bookings that are not expired will be returned

        Args:
            bool_val (bool): when True: return only expired bookings,
            when False: return only non-expired bookings

        Returns:
            QuerySet: the filtered queryset
        """
        if bool_val:
            return self.filter(
                status=Payable.Status.IN_PROGRESS, expires_at__lt=timezone.now()
            )
        return self.filter(
            ~Q(status=Payable.Status.IN_PROGRESS) | Q(expires_at__gt=timezone.now())
        )

    def has_accessibility_info(self, bool_val=True) -> QuerySet:
        """
        Bookings that have accessibility information will be returned

        Args:
            bool_val (bool): when True: return only bookings with accessibility information,
            when False: return only bookings without accessibility information

        Returns:
            QuerySet: the filtered queryset
        """
        return self.exclude(accessibility_info__isnull=bool_val)


def generate_expires_at():
    """Generates the expires at timestamp for a booking"""
    return timezone.now() + datetime.timedelta(minutes=15)


BookingManager = models.Manager.from_queryset(BookingQuerySet)


# pylint: disable=too-many-public-methods
class Booking(TimeStampedMixin, Payable):
    """A booking for a performance

    A booking holds a collection of tickets for a given performance.

    Note:
        A user can only have 1 In Progress booking per performance.
    """

    objects: models.Manager = BookingManager()  # type: ignore

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["status", "performance", "user_id"],
                condition=models.Q(status="IN_PROGRESS"),
                name="one_in_progress_booking_per_user_per_performance",
            )
        ]
        permissions = (("refund_booking", "Can refund booking"),)

    reference = models.CharField(
        default=create_short_uuid, editable=False, max_length=12, unique=True
    )

    performance = models.ForeignKey(
        Performance,
        on_delete=models.RESTRICT,
        related_name="bookings",
    )

    # An additional discount that can be applied to the booking by an admin
    # To create a concession ticket a 100% discount can be applied.
    admin_discount_percentage = models.FloatField(
        default=0, validators=[MaxValueValidator(1), MinValueValidator(0)]
    )

    # Accessibility information for the booking
    # We store the previous accessibility information so that production staff
    # can see what has changed when they get an email letting them know
    # that the accessibility information has changed.
    accessibility_info = models.TextField(null=True, blank=True)
    accessibility_info_updated_at = models.DateTimeField(null=True, blank=True)
    previous_accessibility_info = models.TextField(null=True, blank=True)

    expires_at = models.DateTimeField(default=generate_expires_at)

    @property
    def payment_reference_id(self):
        return self.reference

    def __str__(self):
        return str(self.reference)

    def get_concession_map(self) -> Dict["ConcessionType", int]:
        """Get map of number of concessions in this booking

        Returns:
            dict of ConcessionType: int: The number of each ConcessionType
                in this Booking.
        """
        booking_concessions: Dict = {}
        for ticket in self.tickets.all():
            if (
                not ticket.concession_type
                in booking_concessions.keys()  # pylint: disable=consider-iterating-dictionary
            ):
                booking_concessions[ticket.concession_type] = 0
            booking_concessions[ticket.concession_type] += 1
        return booking_concessions

    def is_valid_discount_combination(self, discounts: DiscountCombination) -> bool:
        """Check if a provided discount combination is valid

        A discount combination is valid if the booking has enough of each
        ConcessionType to meet the discount requirements of the discount
        combination.

        Args:
            discounts (DiscountCombination): The DiscountCombination being
                checked against the booking.

        Returns:
            bool: Whether the provided DiscountCombination is valid for the
                Booking.
        """
        concession_requirements = discounts.get_concession_map()
        booking_concessions = self.get_concession_map()
        return not any(
            concession_requirements[requirement]
            > booking_concessions.get(requirement, 0)
            for requirement in concession_requirements.keys()
        )

    def get_valid_discounts(self) -> List[DiscountCombination]:
        """Return a list of valid discount combinations for the booking

        Returns:
            list of DiscountCombination: The list of valid
                DiscountCombinations which can be applid to this Booking.
        """
        return [
            DiscountCombination(discounts)
            for discounts in combinations(
                list(self.performance.discounts.all()),
                self.tickets.count(),
            )
            if self.is_valid_discount_combination(DiscountCombination(discounts))
        ]

    def get_price(self) -> int:
        """Price of the booking with no discounts applied

        Returns the price of the all the seats in the booking, with no
        discounts applied.

        Returns:
            int: Price of all the Booking's seats in penies.
        """
        return sum(ticket.seat_price() for ticket in self.tickets.all())

    def tickets_price(self) -> int:
        """Price of booking with single discounts applied.

        Get the price of the booking with only single discounts (those applying
        to only one ticket) applied.

        Returns:
            int: Price of the Booking with single discounts.
        """
        return sum(
            ticket.discounted_price(single_discounts_map=self.single_discounts_map)
            for ticket in self.tickets.all()
        )

    @cached_property
    def single_discounts_map(self) -> Dict["ConcessionType", float]:
        """Get the discount value for each concession type from the performance model

        Returns:
            dict: Map of concession types to thier single discount percentage

        """
        return self.performance.single_discounts_map

    def get_price_with_discount_combination(
        self, discounts: DiscountCombination
    ) -> int:
        """Price with a DiscoutnCombination applied

        Given a discount combination return the price of the booking in penies
        with that discount combination applied. The DiscountCombination must be
        valid.

        Args:
            (DiscountCombination): The discount combination to apply to the
                Booking.

        Returns:
            int: Price of the Booking with given DiscountCombination applied.
        """
        assert self.is_valid_discount_combination(discounts)

        discount_total: int = 0
        tickets_available_to_discount = list(self.tickets.all())
        for discount_from_comb in discounts.discount_combination:
            discount = DiscountCombination((discount_from_comb,))
            concession_map = discount.get_concession_map()
            for concession_type, number in concession_map.items():
                for _ in range(number):
                    # Skipped coverage here as there is no way that the next
                    # could not get an item (hopefully) given that the discount
                    # is valid.
                    ticket = next(  # pragma: no cover
                        ticket
                        for ticket in tickets_available_to_discount
                        if ticket.concession_type == concession_type
                    )
                    discount_total += math.floor(
                        self.performance.performance_seat_groups.get(
                            seat_group=ticket.seat_group
                        ).price
                        * discount_from_comb.percentage
                    )
                    tickets_available_to_discount.remove(ticket)
        # For each type of concession
        return self.get_price() - discount_total

    def get_best_discount_combination(self) -> Optional[DiscountCombination]:
        """DiscountCombination which minimises price of Booking

        Returns the discount combination which when applied to the booking
        gives the largest discount.

        Returns:
            (DiscountCombination): The valid DiscountCombination which
                minimises the price of the Booking.
        """
        return self.get_best_discount_combination_with_price()[0]

    @cached_property
    # pylint: disable=invalid-overridden-method
    def subtotal(self) -> int:  # type: ignore
        """Price of the booking with discounts applied.

        Returns the subtotal of the booking. This is the total value including
        single and group discounts before any misc costs are applied.
        If an admin discount is also applied this will be added here.

        Returns:
            int: price of the booking with discounts applied in penies
        """
        if self.performance.has_group_discounts:
            discounted_price = self.get_best_discount_combination_with_price()[1]
        else:
            discounted_price = self.tickets_price()
        return math.ceil(discounted_price * (1 - self.admin_discount_percentage))

    def get_best_discount_combination_with_price(
        self,
    ) -> Tuple[Optional[DiscountCombination], int]:
        """DiscountCombination and its price which minimises price of Booking

        Returns the discount combination, and the price of the booking with it
        applied, which when applied to the booking gives the largest discount.

        Returns:
            (DiscountCombination): The valid DiscountCombination which
                minimises the price of the Booking.
            (int): The price of the Booking with the best DiscountCombination
                applied.
        """
        best_price = self.get_price()
        best_discount: Optional[DiscountCombination] = None
        for discount_combo in self.get_valid_discounts():
            discount_combo_price = self.get_price_with_discount_combination(
                discount_combo
            )
            if discount_combo_price < best_price:
                best_price = discount_combo_price
                best_discount = discount_combo

        return best_discount, best_price

    def discount_value(self) -> int:
        """The value of group discounts on the booking.

        When checking the subtotal of the booking (the price with all Discounts
        applied), check the value of the discounts. This value does not include
        single discounts. (i.e. if only single discounts were applied the
        discount value would be 0).

        Returns:
            (int): The value in penies of group discounts applied to the Booking.
        """
        return self.tickets_price() - self.subtotal

    @property
    def misc_costs_value(self) -> int:
        """The value of the misc costs applied in pence

        Detetmine the value of the MiscCosts applied to this Booking. Currently
        all MiscCosts are applied to all Bookings. The mist costs are applied
        to the subtotal of the Booking.

        Returns:
            (int): The value in penies of MiscCosts applied to the Booking
        """
        return MiscCost.objects.all().value(self)

    def get_ticket_diff(
        self, tickets: Union[List["Ticket"], Iterable["Ticket"]]
    ) -> Tuple[List["Ticket"], List["Ticket"], int]:
        """Difference between Booking Tickets and list of Tickets

        Given a list of Tickets return the difference between the two lists.
        The difference is returned as 2 lists. The first list contains the
        tickets which are not in the booking and the second those which are in
        the booking but not in the list.

        To make the Booking match the provided list, the Tickets returned in
        the first list should be created (and added to the Booking) and the
        Tickets in the second list should be deleted.

        Args:
            tickets (list of Ticket): A list of tickets to compare with the Booking's
                tickets.

        Returns:
            list of Ticket: The tickets which are in the provided list but
                not in the Booking.
            list of Ticket: The tickets which are in the booking but not in
                the provided list.
            int: The total number of tickets if this operation is applied
        """
        add_tickets: List["Ticket"] = []
        delete_tickets: List["Ticket"] = []
        existing_tickets: Dict[int, "Ticket"] = {}

        # find tickets to add
        for ticket in tickets:
            # splits requested tickets into id'd and no id'd
            if ticket.id is None:
                # if they have no id, they must be new
                add_tickets.append(ticket)
            else:
                # if they have an id, they must have existed at some point
                existing_tickets[ticket.id] = ticket

        # find tickets to delete
        for ticket in self.tickets.all():
            if existing_tickets.get(ticket.id):
                # if a given booking ticket is in the requested tickets - you keep it -
                existing_tickets.pop(ticket.id, None)
            else:
                # if the ticket exists in the booking, but not in the requested tickets - delete it.
                delete_tickets.append(ticket)

        return (
            add_tickets,
            delete_tickets,
            (len(self.tickets.all()) + len(add_tickets) - len(delete_tickets)),
        )

    def pay(self, payment_method: "PaymentProvider") -> Optional["Transaction"]:
        if self.is_reservation_expired:
            raise CantBePaidForException(
                message="This booking has expired. Please create a new booking"
            )

        return super().pay(payment_method)

    def complete(self, payment: Optional[Transaction] = None):
        """
        Complete the booking (after it has been paid for) and send the
        confirmation email.
        """
        super().complete()

        booking_emails.send_booking_confirmation_email(self, payment)
        if self.accessibility_info:
            booking_emails.send_booking_accessibility_info_email(self)

    def clone(self):
        clone = super().clone()
        clone.reference = create_short_uuid()
        return clone

    @property
    def web_tickets_path(self):
        """Generates the path to the public tickets display page on the frontend for this booking"""
        params = {
            "performanceID": to_global_id("PerformanceNode", self.performance.id),
            "ticketID": [
                to_global_id("TicketNode", id)
                for id in self.tickets.values_list("id", flat=True)
            ],
        }
        return f"/user/booking/{self.reference}/tickets?" + urlencode(params, True)

    @property
    def is_reservation_expired(self):
        """Returns whether the booking is considered expired"""
        return filter_passes_on_model(
            self, lambda qs: qs.expired()  # type:ignore
        )

    def validate_cant_be_refunded(self) -> Optional[CantBeRefundedException]:
        if error := super().validate_cant_be_refunded():
            return error
        if self.performance.production.status in [
            Production.Status.CLOSED,
            Production.Status.COMPLETE,
        ]:
            return CantBeRefundedException(
                f"The Booking ({self}) can't be refunded because of it's performances' status ({self.performance.production.status})"
            )
        return None

    @property
    def can_be_refunded(self):
        return super().can_be_refunded and (
            not self.performance.production.status
            in [Production.Status.CLOSED, Production.Status.COMPLETE]
        )

    @property
    def display_name(self):
        return f"Booking Ref. {self.reference} for {str(self.performance).lower()}"


class TicketQuerySet(QuerySet):
    """A custom Manager for ticket queries"""

    def sold_or_reserved(self) -> QuerySet:
        return self.filter(
            Q(booking__status=Payable.Status.PAID)
            | Q(
                booking__status=Payable.Status.IN_PROGRESS,
                booking__expires_at__gt=timezone.now(),
            )
        )

    def sold(self) -> QuerySet:
        return self.filter(Q(booking__status="PAID"))


TicketManager = models.Manager.from_queryset(TicketQuerySet)


class Ticket(BaseModel):
    """A booking of a single seat.

    A Ticket is the reservation of a seat for a performance. The performance is
    defined by the Booking.
    """

    objects = TicketManager()

    seat_group = models.ForeignKey(
        SeatGroup, on_delete=models.RESTRICT, related_name="tickets"
    )
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="tickets"
    )
    concession_type = models.ForeignKey(
        ConcessionType,
        on_delete=models.RESTRICT,
        related_name="seat_bookings",
    )
    seat = models.ForeignKey(Seat, on_delete=models.RESTRICT, null=True, blank=True)

    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        related_name="tickets_checked_in_by_user",
        null=True,
        blank=True,
    )

    def discounted_price(self, single_discounts_map=None) -> int:
        """Ticket price with single discounts

        Get the price of the ticket if only single discounts (those applying
        to only one ticket) applied.

        Args:
            (single_discounts_map): ap of concession types to thier single discount percentage. (optional)

        Returns:
            (int): Price of the Ticket in penies with single discounts applied.
        """
        if single_discounts_map is None:
            single_discounts_map = self.booking.single_discounts_map

        performance_seat_group = self.booking.performance.performance_seat_groups.get(
            seat_group=self.seat_group
        )
        price = performance_seat_group.price if performance_seat_group else 0

        return math.ceil(
            (1 - single_discounts_map.get(self.concession_type, 0)) * price
        )

    def seat_price(self) -> int:
        """Price of the Seat without Discounts.

        Return the price of the seat which is being booked without applying any discounts.

        Returns:
            (int): Price of the seat in penies without any discounts.
        """
        return self.booking.performance.performance_seat_groups.get(
            seat_group=self.seat_group
        ).price

    @property
    def checked_in(self) -> bool:
        """Boolean property for if a ticket is checked in.

        Returns:
            bool: Whether the ticket is checked in.
        """
        return self.checked_in_at is not None

    def check_in(self, user: User):
        """
        Check a ticket in
        """
        if self.checked_in_at:
            raise GQLException(
                message=f"Ticket of id {self.id} is already checked-in.",
            )

        self.checked_in_at = timezone.now()
        self.checked_in_by = user
        self.save()

    def uncheck_in(self):
        """
        Un-Check a ticket in
        """
        if not self.checked_in_at:
            raise GQLException(
                message=f"Ticket of id {self.id} cannot be un-checked in as it is not checked-in.",
            )

        self.checked_in_at = None
        self.checked_in_by = None
        self.save()

    def __str__(self):
        return "%s | %s" % (self.seat_group.name, self.concession_type.name)
