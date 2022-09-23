from django.db import models

from uobtheatre.payments.exceptions import (
    CantBeCanceledException,
    CantBeRefundedException,
)
from uobtheatre.payments.transaction_providers import (
    Cash,
    PaymentProvider,
    RefundProvider,
    TransactionProvider,
)
from uobtheatre.societies.models import Society
from uobtheatre.users.models import User
from uobtheatre.utils.models import BaseModel, TimeStampedMixin


class FinancialTransfer(TimeStampedMixin, BaseModel):
    """Model for representing the movemement of funds at the business level"""

    class Method(models.TextChoices):
        """Method used for the transfer"""

        INTERNAL = "INTERNAL", "Internal"
        BACS = "BACS", "BACS"

    society = models.ForeignKey(
        Society, on_delete=models.SET_NULL, null=True
    )  # The society being paid to

    value = models.PositiveIntegerField()  # The amount transfered
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True
    )  # The user who recorded the transfer
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
    )
    reason = models.TextField(null=True)  # Optional reason for transfer

    class Meta:
        permissions = (("create_transfer", "Create a transfer entry"),)
