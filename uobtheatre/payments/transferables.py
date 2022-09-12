from typing import TYPE_CHECKING, Optional

from django.db import models

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
        "self", on_delete=models.RESTRICT, null=True, related_name="_transferred_to"
    )

    @property
    def transferred_to(self) -> Optional["Transferable"]:
        """The transfered which this has been transfred to.

        If this has not be transfered None will be returned.

        Note: _transferred_to cannot be used directly as if this booking has not
        been transfered an error is raised.
        """
        if not hasattr(self, "_transferred_to"):
            return None
        return self._transferred_to  # type: ignore

    @property
    def transfer_fee(self) -> int:
        return 200

    @property
    def pre_transfer_total(self) -> int:
        return super().total

    @property
    def total(self) -> int:
        """The total cost of a transferable.

        The final price of the transferable with all dicounts and misc costs
        applied. This is the price the User will be charged.

        This overrides the default payable implementation to include the
        transfer reduction.

        When transfering a payable, all previous payments (excluding
        transfer fees) are provided as a discount to the new payable.

        Returns:
            (int): total price of the transferable in penies
        """
        subtotal = self.subtotal
        if subtotal == 0:  # pylint: disable=comparison-with-callable
            return 0

        if not self.transfered_from:
            return self.pre_transfer_total

        return (
            max(self.pre_transfer_total - self.transfered_from.pre_transfer_total, 0)
            + self.transfer_fee
        )

    class Meta:
        abstract = True
