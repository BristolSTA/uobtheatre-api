import itertools
import uuid
from typing import List, Tuple

from django.db import models

from uobtheatre.productions.models import Performance
from uobtheatre.users.models import User
from uobtheatre.utils.models import SoftDeletionMixin, TimeStampedMixin
from uobtheatre.venues.models import SeatGroup, SeatType


class Discount(models.Model):
    name = models.CharField(max_length=255)
    discount = models.SmallIntegerField()
    performances = models.ManyToManyField(
        Performance, blank=True, related_name="discounts"
    )
    seat_type = models.ForeignKey(
        SeatType, on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return f"{self.discount * 100}% off for {self.name}"


class ConsessionType(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class DiscountRequirement(models.Model):
    number = models.SmallIntegerField()
    discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="discount_requirements"
    )
    consession_type = models.ForeignKey(ConsessionType, on_delete=models.CASCADE)


def combinations(iterable: List, max_length: int) -> List[Tuple]:
    """ Given a list give all the combinations of that list up to a given length """

    return set(
        [
            combination
            for i in range(1, max_length + 1)
            for combination in itertools.combinations(iterable * i, i)
        ]
    )


class DiscountCombination:
    def __init__(self, discount_combination):
        self.discount_combination = discount_combination

    def __eq__(self, obj):
        return (
            isinstance(obj, DiscountCombination)
            and obj.discount_combination == self.discount_combination
        )

    def get_requirements(self):
        return [
            requirement
            for discount in self.discount_combination
            for requirement in discount.discount_requirements.all()
        ]

    def get_consession_map(self):
        """Return a map of how many of each consession type are rquired for
        this discount combination"""
        consession_requirements = {}
        for requirement in self.get_requirements():
            if not requirement.consession_type in consession_requirements.keys():
                consession_requirements[requirement.consession_type] = 0
            consession_requirements[requirement.consession_type] += requirement.number
        return consession_requirements


class Booking(models.Model, TimeStampedMixin):
    """A booking is for one performance and has many tickets"""

    booking_reference = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    performance = models.ForeignKey(
        Performance,
        on_delete=models.RESTRICT,
        related_name="bookings",
    )

    def __str__(self):
        return str(self.booking_reference)

    def get_consession_map(self):
        """ Return the number of each type of consession in this booking """
        booking_consessions = {}
        for seat_booking in self.seat_bookings.all():
            if not seat_booking.consession_type in booking_consessions.keys():
                booking_consessions[seat_booking.consession_type] = 0
            booking_consessions[seat_booking.consession_type] += 1
        return booking_consessions

    def is_valid_discount_combination(self, discounts: DiscountCombination) -> bool:
        consession_requirements = discounts.get_consession_map()
        booking_consessions = self.get_consession_map()
        return not any(
            consession_requirements[requirement]
            > booking_consessions.get(requirement, 0)
            for requirement in consession_requirements.keys()
        )

    def get_valid_discounts(self) -> List[Discount]:
        list(self.performance.discounts.all()),
        return [
            DiscountCombination(discounts)
            for discounts in combinations(
                list(self.performance.discounts.all()),
                self.seat_bookings.count(),
            )
            if self.is_valid_discount_combination(DiscountCombination(discounts))
        ]

    def get_price(self) -> float:
        return sum(
            self.performance.seat_prices.filter(seat_type=seat.seat_group.seat_type)
            .first()
            .price
            for seat in self.seat_bookings.all()
        )

    def get_price_with_discounts(self, discounts: Tuple[DiscountCombination]) -> float:
        discount_total = 0
        seats_available_to_discount = [seat for seat in self.seat_bookings.all()]
        for discount_from_comb in discounts.discount_combination:
            discount = DiscountCombination((discount_from_comb,))
            consession_map = discount.get_consession_map()
            for consession_type in consession_map.keys():
                for i in range(consession_map[consession_type]):
                    seat = next(
                        seat
                        for seat in seats_available_to_discount
                        if seat.consession_type == consession_type
                    )
                    discount_total += (
                        self.performance.seat_prices.filter(
                            seat_type=seat.seat_group.seat_type
                        )
                        .first()
                        .price
                        * discount_from_comb.discount
                    )
                    seats_available_to_discount.remove(seat)
        # For each type of conession
        return self.get_price() - discount_total

    def get_best_discount_combination(self):
        valid_discounts = get_valid_discounts()
        pass


class SeatBooking(models.Model):
    """A booking of a single seat (from a seat group)"""

    seat_group = models.ForeignKey(
        SeatGroup, on_delete=models.RESTRICT, related_name="seat_bookings"
    )
    booking = models.ForeignKey(
        Booking, on_delete=models.PROTECT, related_name="seat_bookings"
    )
    consession_type = models.ForeignKey(
        ConsessionType,
        on_delete=models.SET_NULL,
        related_name="seat_bookings",
        null=True,
    )


class PerformanceSeatPrice(models.Model):
    seat_type = models.ForeignKey(SeatType, on_delete=models.RESTRICT)
    performance = models.ForeignKey(
        Performance, on_delete=models.RESTRICT, related_name="seat_prices"
    )
    price = models.IntegerField()
