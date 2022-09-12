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

from uobtheatre.bookings.exceptions import (
    BookingTransferCheckedInTicketsException,
    BookingTransferPerformanceUnchangedException,
    BookingTransferToDifferentProductionException,
)
from uobtheatre.discounts.models import ConcessionType, DiscountCombination
from uobtheatre.mail.composer import MailComposer
from uobtheatre.payments.exceptions import (
    CantBePaidForException,
    CantBeRefundedException,
    TransferUnpaidPayableException,
)
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable, PayableQuerySet
from uobtheatre.payments.transferables import Transferable
from uobtheatre.productions.exceptions import (
    InvalidConcessionTypeException,
    InvalidSeatGroupException,
    NotBookableException,
    NotEnoughCapacityException,
)
from uobtheatre.productions.models import Performance, Production
from uobtheatre.users.models import User
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

    A misc costs is defined by either a value or a percentage. If both are
    supplied the percentage will take precedence.

    Note:
        Currently all misc costs are applied to all bookings.
    """

    objects = MiscCostManager()

    class Type(models.TextChoices):
        BOOKING = "Booking", "Applied to booking purchase"

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    percentage = models.FloatField(
        null=True, blank=True, validators=[MaxValueValidator(1), MinValueValidator(0)]
    )
    value = models.FloatField(null=True, blank=True)
    type = models.CharField(
        max_length=24,
        choices=Type.choices,
    )

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
        return self.annotate(checked_in=BoolAnd("tickets__checked_in"))

    def annotate_checked_in_count(self) -> QuerySet:
        return self.annotate(count=models.Count("tickets")).annotate(
            checked_in_count=models.Count(
                Case(When(tickets__checked_in=True, then=Value(1)))
            )
        )

    def annotate_checked_in_proportion(self) -> QuerySet:
        # To calculate the proportion of tickets that are checked in you need two values
        # the first - the number of tickets
        # the second - the number of tickets that are checked in
        # Whilst it shouldn't occur a divide by zero is prevented setting to zero when the ticket count is zero
        return self.annotate_checked_in_count().annotate(
            proportion=Case(
                When(Q(count=0), then=Cast(0, FloatField())),
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


def generate_expires_at():
    """Generates the expires at timestamp for a booking"""
    return timezone.now() + timezone.timedelta(minutes=15)


BookingManager = models.Manager.from_queryset(BookingQuerySet)

# pylint: disable=too-many-public-methods
class Booking(TimeStampedMixin, Transferable):
    """A booking for a performance

    A booking holds a collection of tickets for a given performance.

    Note:
        A user can only have 1 In Progress booking per performance.
    """

    objects = BookingManager()  # type: ignore

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["status", "performance", "user_id"],
                condition=models.Q(status="IN_PROGRESS"),
                name="one_in_progress_booking_per_user_per_performance",
            )
        ]

    reference = models.CharField(
        default=create_short_uuid, editable=False, max_length=12, unique=True
    )

    # Stores who created the booking
    # For regular bookings this will be the user
    # For boxoffice bookings it will be the logged in boxoffice user
    # For admin bookings it will be the logged in admin
    creator = models.ForeignKey(
        User, on_delete=models.RESTRICT, related_name="created_bookings"
    )

    performance = models.ForeignKey(
        Performance,
        on_delete=models.RESTRICT,
        related_name="bookings",
    )

    # TODO Can this be moved to payable?
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")

    # An additional discount that can be applied to the booking by an admin
    # To create a concession ticket a 100% discount can be applied.
    admin_discount_percentage = models.FloatField(
        default=0, validators=[MaxValueValidator(1), MinValueValidator(0)]
    )

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

    # pylint: disable=invalid-overridden-method
    @cached_property
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
    def misc_cost_types(self) -> List[MiscCost.Type]:
        misc_cost_types = [MiscCost.Type.BOOKING]
        # If this booking is transfered from another then transfer misc costs
        # should also be applied
        return misc_cost_types

    @property
    def misc_costs_value(self) -> int:
        """The value of the misc costs applied in pence

        Detetmine the value of the MiscCosts applied to this Booking. Currently
        all MiscCosts are applied to all Bookings. The mist costs are applied
        to the subtotal of the Booking.

        Returns:
            (int): The value in penies of MiscCosts applied to the Booking
        """
        return MiscCost.objects.filter(type__in=self.misc_cost_types).value(self)

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

        # If this is a transfer and the booking it is transfered from is not paid
        if self.transfered_from:
            self.transfered_from.check_can_transfer_to(
                self.performance
            )  # pylint: disable=protected-access

        return super().pay(payment_method)

    def complete(self, payment: Transaction = None):
        """
        Complete the booking (after it has been paid for) and send the
        confirmation email.
        """
        super().complete()

        # If the booking is transfered from another
        if self.transfered_from:
            self.transfered_from.status = Booking.Status.CANCELLED
            self.transfered_from.save()

        self.send_confirmation_email(payment)

    def clone(self):
        clone = super().clone()
        clone.reference = create_short_uuid()
        return clone

    def check_can_transfer_to(self, performance: "Performance") -> None:
        """Check if a booking can be transfered to the provided performance.

        If not an error is raised. Note this function must be called both
        before a transfer booking is created and before a transfer booking is
        paid for (as between creating and paying for a transfer thing could
        change e.g. the original booking could be used or refunded)
        """

        # If the booking is not paid it cannot be transfered
        if self.status != Payable.Status.PAID:
            raise TransferUnpaidPayableException(self.get_status_display())

        # If any of the bookings tickets are checked in then this booking
        # cannot be transfered
        if self.tickets.filter(checked_in=True).exists():
            raise BookingTransferCheckedInTicketsException()

        # Cannot transfer to the same performance
        if self.performance == performance:
            raise BookingTransferPerformanceUnchangedException

        # Cannot transfer to a differnet production
        if self.performance.production != performance.production:
            raise BookingTransferToDifferentProductionException

    def create_transfer(self, performance: "Performance") -> "Booking":
        """
        Create an in progress booking to transfer the booking to a different
        performance.

        This is a new booking which copies the attributes from the original and
        with the transfered_from attribute equal to the new booking. This new
        booking will be IN_PROGRESS and the transfere will not be completed
        until the new booking is COMPLETE.

        Once the new booking is COMPLETE, the original booking will be
        cancelled.
        """

        self.check_can_transfer_to(performance)

        # This will delete any exisiting IN_PROGRESS booking that the user has
        # for this performance (this includes transfers)
        self.user.bookings.filter(
            status=Payable.Status.IN_PROGRESS, performance_id=performance.id
        ).delete()

        # Create the new booking to transfer to
        new_booking = self.clone()
        new_booking.status = Payable.Status.IN_PROGRESS
        new_booking.performance = performance
        new_booking.transfered_from = self
        new_booking.admin_discount_percentage = 0
        new_booking.expires_at = generate_expires_at()
        new_booking.save()

        # Copy across all tickets which can be copied one by one
        for ticket in self.tickets.all():
            # If there is capcity for this ticket in the other performance then
            # copy this ticket to the new booking
            try:
                performance.validate_tickets(ticket.qs)

                # Clone ticket to new booking
                new_ticket = ticket.clone()
                new_ticket.booking = new_booking
                new_ticket.save()
            except (
                NotEnoughCapacityException,
                InvalidSeatGroupException,
                InvalidConcessionTypeException,
            ) as exc:
                print(
                    f"Not copying accross ticket {ticket.seat_group} as {exc.__class__}"
                )

        return new_booking

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

    def send_confirmation_email(self, payment: Transaction = None):
        """
        Send email confirmation which includes a link to the booking.
        """
        composer = MailComposer()

        if self.transfered_from:
            composer.line(
                "Your booking transfer to %s has been confirmed!"
                % self.performance.production.name
            )
        else:
            composer.line(
                "Your booking to %s has been confirmed!"
                % self.performance.production.name
            )

        if self.performance.production.featured_image:
            composer.image(self.performance.production.featured_image.file.url)

        composer.line(
            (
                "This event opens at %s for a %s start. Please bring your tickets (printed or on your phone) or your booking reference (<strong>%s</strong>)."
                if self.user.status.verified  # type: ignore
                else "This event opens at %s for a %s start. Please bring your booking reference (<strong>%s</strong>)."
            )
            % (
                self.performance.doors_open.astimezone(  # type: ignore
                    self.performance.venue.address.timezone  # type: ignore
                ).strftime("%d %B %Y %H:%M %Z"),
                self.performance.start.astimezone(  # type: ignore
                    self.performance.venue.address.timezone  # type: ignore
                ).strftime("%H:%M %Z"),
                self.reference,
            )
        )

        composer.action(self.web_tickets_path, "View Tickets")

        if self.user.status.verified:  # type: ignore
            composer.action("/user/booking/%s" % self.reference, "View Booking")

        # If this booking includes a payment, we will include details of this payment as a reciept
        if payment:
            composer.heading("Payment Information").line(
                f"{payment.value_currency} paid ({payment.provider.description}{' - ID ' + payment.provider_transaction_id if payment.provider_transaction_id else '' })"
            )

        composer.line(
            "If you have any accessability concerns, or otherwise need help, please contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>."
        )

        subject = (
            "Booking transfer complete"
            if self.transfered_from
            else "Your booking is confirmed!"
        )
        composer.send(subject, self.user.email)

    @property
    def is_reservation_expired(self):
        """Returns whether the booking is considered expired"""
        return filter_passes_on_model(self, lambda qs: qs.expired())

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

    checked_in = models.BooleanField(default=False)

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

    def check_in(self):
        """
        Check a ticket in
        """
        self.checked_in = True
        self.save()

    def uncheck_in(self):
        """
        Un-Check a ticket in
        """
        self.checked_in = False
        self.save()

    def __str__(self):
        return "%s | %s" % (self.seat_group.name, self.concession_type.name)
