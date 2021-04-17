from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from uobtheatre.utils.models import TimeStampedMixin


class Payment(TimeStampedMixin, models.Model):
    """The model for a transaction.

    When ever a transaction is made for a Production a Payment object is
    created. This stores the key information about the transaction.
    """

    class PaymentProvider(models.TextChoices):
        """How the payment was made."""

        CASH = "CASH", "Cash"
        SQUARE_ONLINE = "SQUARE_ONLINE", "Square online"
        SQUARE_POS = "SQUARE_POS", "Square point of sale"

    class PaymentType(models.TextChoices):
        """Whether the payment was a refund or purchase."""

        PURCHASE = "PURCHASE", "Purchase payment"
        REFUND = "REFUND", "Refund payment"

    # List of models which can be paid for
    payables = models.Q(app_label="bookings", model="booking")
    # This list can be extended to add additional types e.g.
    # | models.Q(app_label="shop", model="sellableitem")

    pay_object_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=payables,
    )
    pay_object_id = models.PositiveIntegerField()

    # The object that has been payed for. The type of this object has to be of
    # one of the payable types.
    pay_object = GenericForeignKey("pay_object_type", "pay_object_id")

    type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.PURCHASE,
    )

    provider_payment_id = models.CharField(max_length=40, null=True, blank=True)
    provider = models.CharField(
        max_length=20,
        choices=PaymentProvider.choices,
        default=PaymentProvider.SQUARE_ONLINE,
    )

    value = models.IntegerField()
    currency = models.CharField(max_length=10, default="GBP")

    card_brand = models.CharField(max_length=20, null=True, blank=True)
    last_4 = models.CharField(max_length=4, null=True, blank=True)

    def url(self):
        """Payment provider transaction link.

        Returns:
            string, optional: url to provider's payment reference
        """
        if self.provider == self.PaymentProvider.SQUARE_ONLINE:
            return f"https://squareupsandbox.com/dashboard/sales/transactions/{self.provider_payment_id}"
        return None
