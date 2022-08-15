import math
from abc import abstractmethod
from typing import TYPE_CHECKING, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models

from uobtheatre.payments.models import SalesBreakdown, Transaction
from uobtheatre.payments.payables import Payable

if TYPE_CHECKING:
    pass

# pylint: disable=abstract-method
class Transferable(Payable):
    """
    A transferable is a payable which can be transfered. A transfer is a
    to/from another transferable of the same type. For bookings this enables bookings to be updated (chnaged perfomrance)
    """

    # Whether the booking has be transferred to
    transfered_from = models.OneToOneField(
        "self", on_delete=models.RESTRICT, null=True, related_name="_transfered_to"
    )

    @property
    def transfered_to(self) -> Optional["Transferable"]:
        """The transfered which this has been transfred to.

        If this has not be transfered None will be returned.

        Note: _transfered_to cannot be used directly as if this booking has not
        been transfered an error is raised.
        """
        if not hasattr(self, "_transfered_to"):
            return None
        return self._transfered_to  # type: ignore

    @property
    def transfered_from_chain(self) -> list["Transferable"]:
        """
        A booking can be transfered which creates a new booking and cancels the
        existing one. If this booking has been created in a transfer, this
        gives all bookings which this has been transfered from. Multiple are
        possible as a booking which is created in a transfer can it self be
        transfered.

        Returns:
            list[int]: All the bookings in this transfer chain
        """
        if not self.transfered_from:
            return []
        return [self.transfered_from] + self.transfered_from.transfered_from_chain

    @property
    def transfer_reduction(self) -> int:
        """
        When transfering a payable, all previous payments (excluding
        transfer fees) are excluded.
        """
        transactions = Transaction.objects.filter(
            pay_object_type=ContentType.objects.get_for_model(self.__class__),
            pay_object_id__in=map(lambda m: m.pk, self.transfered_from_chain),
            status=Transaction.Status.COMPLETED,
        )
        return transactions.get_sales_breakdown(
            breakdown=SalesBreakdown.NET_TRANSACTIONS
        )

    @property
    def total(self) -> int:
        """The total cost of a transferable.

        The final price of the transferable with all dicounts and misc costs
        applied. This is the price the User will be charged.

        This overrides the default payable implementation to include the
        transfer reduction.

        Returns:
            (int): total price of the transferable in penies
        """
        subtotal = self.subtotal
        if subtotal == 0:  # pylint: disable=comparison-with-callable
            return 0
        return math.ceil(
            max(subtotal - self.transfer_reduction, 0) + self.misc_costs_value
        )

    class Meta:
        abstract = True
