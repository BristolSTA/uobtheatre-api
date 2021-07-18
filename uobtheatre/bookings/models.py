import math
from typing import Dict, List, Optional, Tuple

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from uobtheatre.discounts.models import ConcessionType, DiscountCombination
from uobtheatre.payments.models import Payment
from uobtheatre.payments.square import PaymentProvider
from uobtheatre.productions.models import Performance
from uobtheatre.users.models import User
from uobtheatre.utils.exceptions import SquareException
from uobtheatre.utils.models import TimeStampedMixin, validate_percentage
from uobtheatre.utils.utils import combinations, create_short_uuid
from uobtheatre.venues.models import Seat, SeatGroup


class MiscCost(models.Model):
    """Model for miscellaneous costs for shows

    Additional costs are added to a booking's final total.
    For example: Booking fee/Theatre improvement levy.

    A misc costs is defined by either a value or a percentage. If both are
    supplied the percentage will take precedence.

    Note:
        Currently all misc costs are applied to all bookings.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    percentage = models.FloatField(
        null=True, blank=True, validators=[validate_percentage]
    )
    value = models.FloatField(null=True, blank=True)

    def get_value(self, booking: "Booking") -> int:
        """Calculate the value of the misc cost on a booking.

        Calculate the value of the misc cost given a booking. The value is
        based on the subtotal of the Booking (the price of tickets with
        discounts applied).

        This will always return an value (not optional) as the model is
        required to either have a non null percentage or a non null value

        Args:
            booking (Booking): The booking on which the misc cost is being
                applied.

        Returns:
            int: The value in pennies of the misc cost on this booking.
        """
        if self.percentage is not None:
            return math.ceil(booking.subtotal() * self.percentage)
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


class Booking(TimeStampedMixin, models.Model):
    """A booking for a performance

    A booking holds a collection of tickets for a given performance.

    Note:
        A user can only have 1 In Progress booking per performance.
    """

    class BookingStatus(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        PAID = "PAID", "Paid"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["status", "performance"],
                condition=models.Q(status="IN_PROGRESS"),
                name="one_in_progress_booking_per_user_per_performance",
            )
        ]

    reference = models.CharField(
        default=create_short_uuid, editable=False, max_length=12, unique=True
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")

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
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.IN_PROGRESS,
    )

    payments = GenericRelation(
        Payment, object_id_field="pay_object_id", content_type_field="pay_object_type"
    )

    # An additional discount that can be applied to the booking by an admin
    # To create a concession ticket a 100% discount can be applied.
    admin_discount_percentage = models.FloatField(
        default=0, validators=[validate_percentage]
    )

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
            if not ticket.concession_type in booking_concessions.keys():
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
        return sum(ticket.discounted_price() for ticket in self.tickets.all())

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

    def subtotal(self) -> int:
        """Price of the booking with discounts applied.

        Returns the subtotal of the booking. This is the total value including
        single and group discounts before any misc costs are applied.
        If an admin discount is also applied this will be added here.

        Returns:
            int: price of the booking with discounts applied in penies
        """
        return math.ceil(
            self.get_best_discount_combination_with_price()[1]
            * (1 - self.admin_discount_percentage)
        )

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
        return self.tickets_price() - self.subtotal()

    def misc_costs_value(self) -> int:
        """The value of the misc costs applied in pence

        Detetmine the value of the MiscCosts applied to this Booking. Currently
        all MiscCosts are applied to all Bookings. The mist costs are applied
        to the subtotal of the Booking.

        Returns:
            (int): The value in penies of MiscCosts applied to the Booking
        """
        return sum(misc_cost.get_value(self) for misc_cost in MiscCost.objects.all())

    def total(self) -> int:
        """The total cost of the Booking.

        The final price of the booking with all dicounts and misc costs
        applied. This is the price the User will be charged.

        Returns:
            (int): total price of the booking in penies
        """
        subtotal = self.subtotal()
        if subtotal == 0:
            return 0
        return math.ceil(subtotal + self.misc_costs_value())

    def get_ticket_diff(
        self, tickets: List["Ticket"]
    ) -> Tuple[List["Ticket"], List["Ticket"]]:
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

        return add_tickets, delete_tickets

    def pay(self, nonce: str):
        """Pay for the Booking

        Makes a call to the Square API to pay for the Booking. The price is
        equal to the Booking total.

        Args:
            nonce (str): The nonce provided by the Square payment form on the
                front end.

        Returns:
            Payment: The payment object created by paying for the Booking.

        Raises:
            SquareException:  If the payment is unsucessful.
        """
        response = PaymentProvider.create_payment(
            self.total(), str(self.reference), nonce
        )

        # If the square transaction failed then raise an exception
        if not response.is_success():
            raise SquareException(response)

        # Set the booking as paid
        self.status = self.BookingStatus.PAID
        self.save()

        # Create a payment for this transaction
        card_details = response.body["payment"]["card_details"]["card"]
        amount_details = response.body["payment"]["amount_money"]
        return Payment.objects.create(
            pay_object=self,
            card_brand=card_details["card_brand"],
            last_4=card_details["last_4"],
            provider=Payment.PaymentProvider.SQUARE_ONLINE,
            type=Payment.PaymentType.PURCHASE,
            provider_payment_id=response.body["payment"]["id"],
            value=amount_details["amount"],
            currency=amount_details["currency"],
        )


class Ticket(models.Model):
    """A booking of a single seat.

    A Ticket is the reservation of a seat for a performance. The performance is
    defined by the Booking.
    """

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

    def discounted_price(self) -> int:
        """Ticket price with single discounts

        Get the price of the ticket if only single discounts (those applying
        to only one ticket) applied.

        Returns:
            (int): Price of the Ticket in penies with single discounts applied.
        """
        return self.booking.performance.price_with_concession(
            self.concession_type,
            self.booking.performance.performance_seat_groups.get(
                seat_group=self.seat_group
            ),
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
