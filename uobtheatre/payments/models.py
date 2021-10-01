from typing import Any

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, Sum
from django.db.models.query import QuerySet

from uobtheatre.payments import payment_methods
from uobtheatre.payments.payment_methods import Cash
from uobtheatre.utils.models import TimeStampedMixin


class PaymentQuerySet(QuerySet):
    """The query set for payments"""

    def annotate_sales_breakdown(self, breakdowns: list[str] = None):
        """Annotate sales breakdown onto payments"""
        annotations = {
            k: v
            for k, v in SALE_BREAKDOWN_ANNOTATIOS.items()
            if breakdowns is None or k in breakdowns
        }
        return self.aggregate(**annotations)


class Payment(TimeStampedMixin, models.Model):

    """The model for a transaction.

    When ever a transaction is made for a Production a Payment object is
    created. This stores the key information about the transaction.
    """

    class PaymentType(models.TextChoices):
        """Whether the payment was a refund or purchase."""

        PURCHASE = "PURCHASE", "Purchase payment"
        REFUND = "REFUND", "Refund payment"

    objects = PaymentQuerySet.as_manager()

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
        max_length=20, choices=payment_methods.PaymentMethod.choices
    )

    value = models.IntegerField()
    currency = models.CharField(max_length=10, default="GBP")

    card_brand = models.CharField(max_length=20, null=True, blank=True)
    last_4 = models.CharField(max_length=4, null=True, blank=True)

    # Amount charged by payment provider in GBP
    provider_fee = models.IntegerField(null=True, blank=True)
    # Amount charged by us to process payment
    app_fee = models.IntegerField(null=True, blank=True)

    def url(self):
        """Payment provider transaction link.

        Returns:
            string, optional: url to provider's payment reference
        """
        if self.provider == payment_methods.SquareOnline.name:
            return f"https://squareupsandbox.com/dashboard/sales/transactions/{self.provider_payment_id}"
        return None


SALE_BREAKDOWN_ANNOTATIOS: dict[str, Any] = {
    "total_sales": Sum("value", filter=Q(type=Payment.PaymentType.PURCHASE)),
    "total_card_sales": Sum(
        "value", filter=(~Q(provider=Cash.name) & Q(type=Payment.PaymentType.PURCHASE))
    ),
    # Amount charged by the payment provider (square) for these payments
    "provider_payment_value": Sum(
        "provider_fee", filter=Q(type=Payment.PaymentType.PURCHASE)
    ),
    # Amount we take from net payment - provider cut
    "app_payment_value": (
        Sum("app_fee", filter=Q(type=Payment.PaymentType.PURCHASE))
        - Sum("provider_fee", filter=Q(type=Payment.PaymentType.PURCHASE))
    ),
    "society_transfer_value": (
        Sum(
            "value",
            filter=(~Q(provider=Cash.name) & Q(type=Payment.PaymentType.PURCHASE)),
        )
        - Sum("app_fee")
    ),
    "society_revenue": (
        Sum(
            "value",
            filter=(Q(type=Payment.PaymentType.PURCHASE)),
        )
        - Sum("app_fee")
    ),
}
