import itertools
import math
from typing import Dict, List, Optional, Set, Tuple, TypeVar

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models

from uobtheatre.payments.models import Payment
from uobtheatre.payments.square import PaymentProvider
from uobtheatre.productions.models import Performance
from uobtheatre.users.models import User
from uobtheatre.utils.exceptions import SquareException
from uobtheatre.utils.models import TimeStampedMixin, validate_percentage
from uobtheatre.utils.utils import create_short_uuid
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

    def get_value(self, booking: "bookings.Booking") -> int:
        """Calculate the value of the misc cost on a booking.

        Calculate the value of the misc cost given a booking
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


def get_concession_map(
    requirements: List["DiscountRequirement"],
) -> Dict["ConcessionType", int]:
    """Get map of number of concessions for list discount requirements.

    Given a list of DiscountRequirements return a dict with the number of each
    concession type required.

    Args:
        requirements (:obj:`list` of :obj:`DiscountRequirement`): The list of
        DiscountRequiments which should be counted.

    Returns:
        (dict of ConcessionType: int): The number of each ConcessionType
        required for given list of DiscountRequirements.
    """
    concession_requirements: Dict["ConcessionType", int] = {}
    for requirement in requirements:
        if not requirement.concession_type in concession_requirements.keys():
            concession_requirements[requirement.concession_type] = 0
        concession_requirements[requirement.concession_type] += requirement.number
    return concession_requirements


class Discount(models.Model):
    """A discount which can be applied to a performance's booking.

    Discounts can be applied to a number of performances. They contain a
    percentage, which is the percentage taken off the booking price. 

    A Discount requires a list of DiscountRequiements to be met in order to be
    eligible for a given booking.
    """
    name = models.CharField(max_length=255)
    percentage = models.FloatField()
    performances = models.ManyToManyField(
        Performance,
        blank=True,
        related_name="discounts",
    )
    seat_group = models.ForeignKey(
        SeatGroup, on_delete=models.CASCADE, null=True, blank=True
    )

    def validate_unique(self, *args, **kwargs):
        """Check if another booking with same requirements exists
        
        Extend validate_unique to ensure only 1 discount with the same set of
        requirements can be created.

        Raises:
            ValidationError: If a discount with the same requirements exists.
        """

        super().validate_unique(*args, **kwargs)

        discounts = self.__class__._default_manager.all()
        if not self._state.adding and self.pk is not None:
            discounts = discounts.exclude(pk=self.pk)

        discounts_with_same_requirements = [
            discount
            for discount in discounts
            if discount.get_concession_map() == self.get_concession_map()
        ]
        discounts_with_same_requirements_names = [
            discount.name for discount in discounts_with_same_requirements
        ]

        if len(discounts_with_same_requirements) != 0:
            raise ValidationError(
                f"Discount with given requirements already exists ({','.join(discounts_with_same_requirements_names)})"
            )

    def is_single_discount(self) -> bool:
        """Checks if a discount applies to a single ticket.

        Note:
            Single discounts are used to set the price of a concession ticket.
            e.g. a Student ticket.

        Returns:
            bool: If the booking is a single discount
        """
        return sum(requirement.number for requirement in self.requirements.all()) == 1

    def get_concession_map(
        self,
    ) -> Dict["ConcessionType", int]:
        """Get number of each concession type required for this discount.

        Returns: 
            (dict of ConcessionType: int): The number of each ConcessionType
                required by the discount.
        """
        return get_concession_map(list(self.requirements.all()))

    def __str__(self) -> str:
        return f"{self.percentage * 100}% off for {self.name}"


class ConcessionType(models.Model):
    """A type of person booking a ticket.

    A concession type refers to the type of person booking a ticket.  e.g. a
    student or society member. These concession are used to determine
    discounts.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class DiscountRequirement(models.Model):
    """A requirement for a discount to be eligible for a booking.

    Discount have many discount requirement. A DiscountRequirement stores a
    number of a given concession type required by the booking. If all the
    requirements are met then the discount can be applied to the booking.

    For example:
        - 2x adult 
        - 1x student
    are both valid discount requirements. 

    A discount requirement only maps to a single concession type. For a
    discount to require multiple concession types, it must have multiple
    requirements.

    Note:
        Each concession (ticket) can only be used in a single discount.
    """

    number = models.SmallIntegerField()
    discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="requirements"
    )
    concession_type = models.ForeignKey(ConcessionType, on_delete=models.CASCADE)


T = TypeVar("T")
def combinations(iterable: List[T], max_length: int) -> Set[Tuple[T, ...]]:
    """Return all subsets of input list upto a max length.

    Args:
        iterable (list of Any): The list which is used to find all the subsets.
        max_length (int): The maximum length of the sub sets to return, this
            must be smaller than or equal to the size of the provided iterable.

    Returns:
        (list of tuples of Any): Returns a list containing all the subsets of
            the input list.
    """
    assert max_length <= len(iterable)

    return set(
        combination
        for i in range(1, max_length + 1)
        for combination in itertools.combinations(iterable * i, i)
    )


class DiscountCombination:
    """A wrapper for a list of dicounts

    When discounts are applied to a booking, the best discount combination is
    selected (set of dicounts). A discount combination is simply a list of
    discounts.
    """
    def __init__(self, discount_combination: Tuple[Discount, ...]):
        self.discount_combination = discount_combination

    def __eq__(self, obj) -> bool:
        return (
            isinstance(obj, DiscountCombination)
            and obj.discount_combination == self.discount_combination
        )

    def get_requirements(self) -> List[DiscountRequirement]:
        """Get the requirments for all the discounts

        Returns:
            (list of DiscountRequirement): The list of requirements for all the
                discounts in the discount combination.
        """
        return [
            requirement
            for discount in self.discount_combination
            for requirement in discount.requirements.all()
        ]

    def get_concession_map(self) -> Dict[ConcessionType, int]:
        """
        Return a map of how many of each concession type are rquired for
        this discount combination
        """
        return get_concession_map(self.get_requirements())


class Booking(TimeStampedMixin, models.Model):
    """A booking is for one performance and has many tickets"""

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
        default=create_short_uuid, editable=False, max_length=12
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
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

    def __str__(self):
        return str(self.reference)

    def get_concession_map(self) -> Dict:
        """ Return the number of each type of concession in this booking """
        booking_concessions: Dict = {}
        for ticket in self.tickets.all():
            if not ticket.concession_type in booking_concessions.keys():
                booking_concessions[ticket.concession_type] = 0
            booking_concessions[ticket.concession_type] += 1
        return booking_concessions

    def is_valid_discount_combination(self, discounts: DiscountCombination) -> bool:
        concession_requirements = discounts.get_concession_map()
        booking_concessions = self.get_concession_map()
        return not any(
            concession_requirements[requirement]
            > booking_concessions.get(requirement, 0)
            for requirement in concession_requirements.keys()
        )

    def get_valid_discounts(self) -> List[DiscountCombination]:
        return [
            DiscountCombination(discounts)
            for discounts in combinations(
                list(self.performance.discounts.all()),
                self.tickets.count(),
            )
            if self.is_valid_discount_combination(DiscountCombination(discounts))
        ]

    def get_price(self) -> int:
        """
        Get the price of the booking with no discounts applied.
        """
        return sum(ticket.seat_price() for ticket in self.tickets.all())

    def tickets_price(self) -> int:
        """
        Get the price of the booking if only single discounts (those applying
        to only one ticket) applied.
        """
        return sum(ticket.discounted_price() for ticket in self.tickets.all())

    def get_price_with_discount_combination(
        self, discounts: DiscountCombination
    ) -> int:
        """
        Given a discount combination work out the new subtotal of the booking
        """
        discount_total: int = 0
        tickets_available_to_discount = [ticket for ticket in self.tickets.all()]
        for discount_from_comb in discounts.discount_combination:
            discount = DiscountCombination((discount_from_comb,))
            concession_map = discount.get_concession_map()
            for concession_type in concession_map.keys():
                for _ in range(concession_map[concession_type]):
                    # Skipped coverage here as there is no way that the next could not get an item (hopefully)
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
        """
        Returns the discount combination applied to the discount to get the
        subtotal. This is the discount combination with the greatest value.
        """
        return self.get_best_discount_combination_with_price()[0]

    def subtotal(self) -> int:
        """
        Returns the subtotal of the booking. This is the total value including
        single and group discounts before any misc costs are applied.
        """
        return self.get_best_discount_combination_with_price()[1]

    def get_best_discount_combination_with_price(
        self,
    ) -> Tuple[Optional[DiscountCombination], int]:
        """
        Returns the discounted price (subtotal) and the discount combination
        used to create that price.
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
        """
        Returns the value of the group discounts applied in pence
        """
        return self.tickets_price() - self.subtotal()

    def misc_costs_value(self) -> int:
        """
        Returns the value of the misc costs applied in pence
        """
        return sum(misc_cost.get_value(self) for misc_cost in MiscCost.objects.all())

    def total(self) -> int:
        """
        The final price of the booking with all dicounts and misc costs applied.
        """
        return math.ceil(self.subtotal() + self.misc_costs_value())

    def get_ticket_diff(
        self, tickets: List["Ticket"]
    ) -> Tuple[List["Ticket"], List["Ticket"]]:
        """
        Given a list of tickets return the tickets which need to be created a
        deleted, in two lists.
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
    """A booking of a single seat (from a seat group)"""

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

    def discounted_price(self) -> int:
        """
        Get the price of the ticket if only single discounts (those applying
        to only one ticket) applied.
        """
        return self.booking.performance.price_with_concession(
            self.concession_type,
            self.booking.performance.performance_seat_groups.get(
                seat_group=self.seat_group
            ).price,
        )

    def seat_price(self) -> int:
        """
        Get the price of the ticket with no discounts applied.
        """
        return self.booking.performance.performance_seat_groups.get(
            seat_group=self.seat_group
        ).price
