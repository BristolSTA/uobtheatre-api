from typing import Dict, List, Tuple

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from uobtheatre.productions.models import Performance
from uobtheatre.venues.models import SeatGroup


class ConcessionType(models.Model):
    """A type of person booking a ticket.

    A concession type refers to the type of person booking a ticket.  e.g. a
    student or society member. These concession are used to determine
    discounts.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return str(self.name)


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
        if (
            not requirement.concession_type
            in concession_requirements.keys()  # pylint: disable=consider-iterating-dictionary
        ):
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

    name = models.CharField(max_length=255, null=True)
    percentage = models.FloatField(
        validators=[MaxValueValidator(1), MinValueValidator(0)]
    )
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

        discounts = self.__class__._default_manager.all()  # pylint: disable=W0212
        if not self._state.adding and self.pk is not None:
            discounts = discounts.exclude(pk=self.pk)

        discounts_with_same_requirements = [
            discount
            for discount in discounts
            if discount.get_concession_map() == self.get_concession_map()
            and (
                self.pk
                and len(self.performances.all()) > 0
                and len(discount.performances.all() & self.performances.all()) > 0
            )
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
    concession_type = models.ForeignKey(
        ConcessionType, on_delete=models.CASCADE, related_name="discount_requirements"
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
        """Get map of number of concessions required for this discount

        Returns:
            (dict of ConcessionType: int): The number of each ConcessionType
                required by this Discount.
        """
        return get_concession_map(self.get_requirements())
