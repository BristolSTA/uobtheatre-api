import itertools
import math
import uuid
from typing import Dict, List, Optional, Set, Tuple

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from uobtheatre.payments.models import Payment
from uobtheatre.payments.square import PaymentProvider
from uobtheatre.productions.models import Performance
from uobtheatre.users.models import User
from uobtheatre.utils.exceptions import SquareException
from uobtheatre.utils.models import TimeStampedMixin, validate_percentage
from uobtheatre.venues.models import Seat, SeatGroup


class MiscCost(models.Model):
    """
    Model for miscellaneous costs for shows
    e.g. Booking fee/Theatre improvement levy
    """

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    percentage = models.FloatField(
        null=True, blank=True, validators=[validate_percentage]
    )
    value = models.FloatField(null=True, blank=True)

    def get_value(self, booking) -> float:
        """
        Calculate the value of the misc cost given a booking
        This will always return an value (not optional) as the model is
        required to either have a non null percentage or a non null value
        """
        if self.percentage is not None:
            return booking.subtotal() * self.percentage
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


class Discount(models.Model):
    name = models.CharField(max_length=255)
    discount = models.FloatField()
    performances = models.ManyToManyField(
        Performance,
        blank=True,
        related_name="discounts",
    )
    seat_group = models.ForeignKey(
        SeatGroup, on_delete=models.CASCADE, null=True, blank=True
    )

    def is_single_discount(self) -> bool:
        """
        Retruns True if this discount applys to a single ticket.
        """
        return (
            sum(requirement.number for requirement in self.discount_requirements.all())
            == 1
        )

    def __str__(self) -> str:
        return f"{self.discount * 100}% off for {self.name}"


class ConcessionType(models.Model):
    """
    A concession type refers to the type of person booking a ticket.  e.g. a
    student or society member.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class DiscountRequirement(models.Model):
    number = models.SmallIntegerField()
    discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="discount_requirements"
    )
    concession_type = models.ForeignKey(ConcessionType, on_delete=models.CASCADE)


def combinations(iterable: List, max_length: int) -> Set[Tuple]:
    """ Given a list give all the combinations of that list up to a given length """

    return set(
        combination
        for i in range(1, max_length + 1)
        for combination in itertools.combinations(iterable * i, i)
    )


class DiscountCombination:
    def __init__(self, discount_combination):
        self.discount_combination = discount_combination

    def __eq__(self, obj) -> bool:
        return (
            isinstance(obj, DiscountCombination)
            and obj.discount_combination == self.discount_combination
        )

    def get_requirements(self) -> List[DiscountRequirement]:
        return [
            requirement
            for discount in self.discount_combination
            for requirement in discount.discount_requirements.all()
        ]

    def get_concession_map(self) -> Dict:
        """Return a map of how many of each concession type are rquired for
        this discount combination"""
        concession_requirements: Dict["ConcessionType", int] = {}
        for requirement in self.get_requirements():
            if not requirement.concession_type in concession_requirements.keys():
                concession_requirements[requirement.concession_type] = 0
            concession_requirements[requirement.concession_type] += requirement.number
        return concession_requirements


class Booking(TimeStampedMixin, models.Model):
    """A booking is for one performance and has many tickets"""

    class BookingStatus(models.TextChoices):
        INPROGRESS = "INPROGRESS", "In Progress"
        PAID = "PAID", "Paid"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["status", "performance"],
                condition=models.Q(status="INPROGRESS"),
                name="one_in_progress_booking_per_user_per_performance",
            )
        ]

    booking_reference = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    performance = models.ForeignKey(
        Performance,
        on_delete=models.RESTRICT,
        related_name="bookings",
    )
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.INPROGRESS,
    )

    payments = GenericRelation(
        Payment, object_id_field="pay_object_id", content_type_field="pay_object_type"
    )

    def __str__(self):
        return str(self.booking_reference)

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

    def get_price(self) -> float:
        return sum(
            self.performance.performance_seat_groups.get(
                seat_group=ticket.seat_group.pk
            ).price
            for ticket in self.tickets.all()
        )

    def tickets_price(self) -> float:
        """
        Get the price of the booking if only single discounts (those applying
        to only one ticket) applied.
        """
        return sum(
            self.performance.price_with_concession(
                ticket.concession_type,
                self.performance.performance_seat_groups.get(
                    seat_group=ticket.seat_group.pk
                ).price,
            )
            for ticket in self.tickets.all()
        )

    def get_price_with_discount_combination(
        self, discounts: DiscountCombination
    ) -> float:
        """
        Given a discount combination work out the new subtotal of the booking
        """
        discount_total = 0
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
                    discount_total += (
                        self.performance.performance_seat_groups.get(
                            seat_group=ticket.seat_group
                        ).price
                        * discount_from_comb.discount
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

    def subtotal(self) -> float:
        """
        Returns the subtotal of the booking. This is the total value including
        single and group discounts before any misc costs are applied.
        """
        return self.get_best_discount_combination_with_price()[1]

    def get_best_discount_combination_with_price(
        self,
    ) -> Tuple[Optional[DiscountCombination], float]:
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

    def discount_value(self) -> float:
        """
        Returns the value of the group discounts applied in pence
        """
        return self.tickets_price() - self.subtotal()

    def misc_costs_value(self) -> float:
        """
        Returns the value of the misc costs applied in pence
        """
        return sum(misc_cost.get_value(self) for misc_cost in MiscCost.objects.all())

    def total(self) -> float:
        """
        The final price of the booking with all dicounts and misc costs applied.
        """
        return math.ceil(self.subtotal() + self.misc_costs_value())

    def get_ticket_diff(self, tickets):
        """
        Given a list of tickets return the tickets which need to be created a
        deleted, in two lists.
        """

        addTickets = []
        deleteTickets = []
        newTickets = {}

        for ticket in tickets:

            if ticket.id is None:
                addTickets.append(ticket)
            else:
                newTickets[ticket.id] = ticket

        for ticket in self.tickets.all():

            if newTickets.get(ticket.id):
                newTickets.pop(ticket.id, None)
            else:
                deleteTickets.append(ticket)

        addTickets += newTickets.values()

        return addTickets, deleteTickets

    def pay(self, nonce):
        response = PaymentProvider.create_payment(
            self.total(), str(self.booking_reference), nonce
        )

        if response.is_success():
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

        else:
            # If the square transaction failed then raise an exception
            raise SquareException(response)


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

    def __eq__(self, other):
        """
        Two tickets are equal if the following match:
        - seat_group
        - concession_type
        - seat
        """
        # Attributes required to match
        attributes = ["seat_group", "concession_type", "seat"]
        return all(
            getattr(self, attribute) == getattr(other, attribute)
            for attribute in attributes
        )
