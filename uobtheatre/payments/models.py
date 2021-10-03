from typing import Any

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet

from uobtheatre.payments import payment_methods
from uobtheatre.payments.payment_methods import Cash
from uobtheatre.utils.models import TimeStampedMixin


class PaymentQuerySet(QuerySet):
    """The query set for payments"""

    def annotate_sales_breakdown(self, breakdowns: list[str] = None):
        """Annotate sales breakdown onto payments"""
        annotations = {
            k: Coalesce(v, 0)
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

    @staticmethod
    def handle_update_payment_webhook(request):
        square_payment = request["object"]["payment"]
        payment = Payment.objects.get(provider_payment_id=square_payment["id"])
        payment.update_from_square_payment(square_payment)

    def update_from_square_payment(self, square_payment: dict):
        """
        Given a square payment object, update the payment details.

        Parameters:
            square_payment (dict): Payment object returned from square
        """
        # Set processing fee
        if processing_fee := square_payment.get("processing_fee"):
            self.provider_fee = sum(
                fee["amount_money"]["amount"] for fee in processing_fee
            )
        self.save()

    def update_from_square(self):
        if self.provider_payment_id is not None:
            response = payment_methods.SquareOnline.get_payment(
                self.provider_payment_id
            )
            self.update_from_square_payment(response.body["payment"])


TOTAL_PROVIDER_FEE = Coalesce(
    Sum(
        "provider_fee",
        filter=Q(type=Payment.PaymentType.PURCHASE),
    ),
    0,
)
TOTAL_SALES = Sum("value", filter=Q(type=Payment.PaymentType.PURCHASE))
TOTAL_CARD_SALES = Sum(
    "value", filter=(~Q(provider=Cash.name) & Q(type=Payment.PaymentType.PURCHASE))
)
APP_FEE = Coalesce(Sum("app_fee", filter=Q(type=Payment.PaymentType.PURCHASE)), 0)

SALE_BREAKDOWN_ANNOTATIOS: dict[str, Any] = {
    "total_sales": TOTAL_SALES,
    "total_card_sales": TOTAL_CARD_SALES,
    # Amount charged by the payment provider (square) for these payments
    "provider_payment_value": TOTAL_PROVIDER_FEE,
    # Amount we take from net payment - provider cut
    "app_payment_value": APP_FEE - TOTAL_PROVIDER_FEE,
    "society_transfer_value": TOTAL_CARD_SALES - APP_FEE,
    "society_revenue": TOTAL_SALES - APP_FEE,
}
