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

    print(f"iterable is {iterable}")
    print(f"max_length is: {max_length}")
    return set(
        [
            combination
            for i in range(1, max_length + 1)
            for combination in itertools.combinations(iterable * i, i)
        ]
    )


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

    def is_valid_discount_combination(self, discounts: Tuple) -> bool:
        print(f"discounts are {discounts}")
        print(f"discounts are {discounts[0].discount_requirements.all()}")
        discount_requirements = [
            requirement
            for discount in discounts
            for requirement in discount.discount_requirements.all()
        ]
        print(f"discount requirements are {discount_requirements}")
        consession_requirements = {}
        for requirement in discount_requirements:
            if not requirement.consession_type in consession_requirements.keys():
                consession_requirements[requirement.consession_type] = 0
            consession_requirements[requirement.consession_type] += requirement.number

        print(f"Consession requirements are: {consession_requirements}")

        booking_consessions = {}
        for seat_booking in self.seat_bookings.all():
            if not seat_booking.consession_type in booking_consessions.keys():
                booking_consessions[seat_booking.consession_type] = 0
            booking_consessions[seat_booking.consession_type] += 1

        print(f"Booking consessions are: {booking_consessions}")

        return not any(
            consession_requirements[requirement]
            > booking_consessions.get(requirement, 0)
            for requirement in consession_requirements.keys()
        )

    def get_valid_discounts(self) -> List[Discount]:
        list(self.performance.discounts.all()),
        return [
            discounts
            for discounts in combinations(
                list(self.performance.discounts.all()),
                self.seat_bookings.count(),
            )
            if self.is_valid_discount_combination(discounts)
        ]

    def get_price(self):
        return sum(
            self.performance.seat_prices.filter(seat_type=seat.seat_group.seat_type)
            .first()
            .price
            for seat in self.seat_bookings.all()
        )

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
