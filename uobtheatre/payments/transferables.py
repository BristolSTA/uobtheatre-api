from typing import Optional

from django.db import models
from django.contrib.contenttypes.models import ContentType

from uobtheatre.utils.models import AbstractModelMeta
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.models import Transaction, SalesBreakdown


class Transferable(Payable, metaclass=AbstractModelMeta):  # type: ignore
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
        if not hasattr(self, "_transfered_to"):
            return None
        return self._transfered_to

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
        return [self.transfered_from] + self.transfered_from.transfered_from_bookings

    @property
    def transfer_reduction(self) -> int:
        """
        When transfering a payable, all previous payments (excluding
        transfer fees) are excluded.
        """
        transactions = Transaction.objects.filter(
            pay_object_type=ContentType.objects.get_for_model(self.__class__),
            pay_object_id__in=map(lambda m: m.id, self.transfered_from_chain),
            status=Transaction.Status.COMPLETED,
        )
        return transactions.get_sales_breakdown(
            breakdown=SalesBreakdown.NET_TRANSACTIONS
        )

    class Meta:
        abstract = True
