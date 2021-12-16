from typing import Any

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet

from uobtheatre.payments import payment_methods
from uobtheatre.payments.payment_methods import (
    Cash,
    PaymentMethod,
    RefundMethod,
    SquareOnline,
    SquarePaymentMethodMixin,
    SquarePOS,
)
from uobtheatre.utils.exceptions import GQLException
from uobtheatre.utils.models import TimeStampedMixin


class PaymentQuerySet(QuerySet):
    """The query set for payments"""

    def annotate_sales_breakdown(self, breakdowns: list[str] = None):
        """Annotate sales breakdown onto payments"""
        annotations = {
            k: Coalesce(v, 0)
            for k, v in SALE_BREAKDOWN_ANNOTATIONS.items()
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

    class PaymentStatus(models.TextChoices):
        """The status of the payment."""

        PENDING = "PENDING", "In progress"
        COMPLETED = "COMPLETED", "Completed"

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
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.COMPLETED,
    )

    provider_payment_id = models.CharField(max_length=128, null=True, blank=True)
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

    @classmethod
    def sync_payments(cls):
        """
        Sync all (non manual) payments with their providers. Currently the only
        syncing we do is for the processing fee.
        """

        for payment in cls.objects.filter(
            provider_fee=None,
            provider__in=[
                method.name
                for method in PaymentMethod.non_manual_methods  # pylint: disable=not-an-iterable
            ],
        ):
            payment.sync_payment_with_provider()

    @property
    def provider_class(self):
        return next(
            method for method in PaymentMethod.__all__ if method.name == self.provider
        )

    def url(self):
        """Payment provider transaction link.

        Returns:
            string, optional: url to provider's payment reference
        """
        if self.provider == payment_methods.SquareOnline.name:
            return f"https://squareupsandbox.com/dashboard/sales/transactions/{self.provider_payment_id}"
        return None

    @property
    def value_currency(self):
        return f"{round(self.value / 100)} {self.currency}"

    @staticmethod
    def handle_update_payment_webhook(request):
        """
        Handle an update payment webhook from square.

        Args:
            request (dict): The body of the square webhook
        """
        square_payment = request["object"]["payment"]

        # Get payment id. if the payment is part of a terminal checkout it will
        # have id stored in `terminal_checkout_id` else it will be a regular
        # payment and id will be stored in `id`
        if checkout_id := square_payment.get("terminal_checkout_id"):
            payment_id = checkout_id
            # The data in the webhook is the payment data not the data for the
            # overall checkout so we cannot use it. If we give the below method
            # no data it goes and get what is needs so we can just do that.
            data = None
        else:
            payment_id = square_payment["id"]
            # Here we have all the data we need so we can just parse that into
            # the sync payment method to avoid an extra call to square.
            data = square_payment

        payment = Payment.objects.get(provider_payment_id=payment_id)
        payment.sync_payment_with_provider(data=data)

    @staticmethod
    def handle_update_refund_webhook(request):
        """
        Handle an update refund webhook from square.

        Args:
            request (dict): The body of the square webhook
        """
        provider_refund = request["object"]["refund"]

        payment = Payment.objects.get(
            provider_payment_id=provider_refund["id"], type=Payment.PaymentType.REFUND
        )
        payment.provider_class.refund_method.update_refund(payment, provider_refund)

    def sync_payment_with_provider(self, data=None):
        """Sync the payment with the provider payment

        NOTE: Currently this method only updates the processing_fee of the
        payment.
        """
        if self.provider_payment_id is not None:
            processing_fee = self.provider_class.get_processing_fee(
                str(self.provider_payment_id), data=data
            )
            self.provider_fee = processing_fee

        self.save()

    def cancel(self):
        """
        Cancel payment

        This is currently only possible for SquarePOS payments that are
        pending.
        """
        if self.status == Payment.PaymentStatus.PENDING:
            self.provider_class.cancel(self)
            self.delete()

    def refund(self, refund_method: RefundMethod = None):
        if self.status != Payment.PaymentStatus.COMPLETED:
            raise GQLException(f"You cannot refund a {self.status.value} payment")

        if not self.provider_class.is_refundable:
            raise GQLException(f"A {self.provider} payment is not refundable")

        if not refund_method:
            refund_method = self.provider_class.refund_method
        refund_method.refund(self)


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

SALE_BREAKDOWN_ANNOTATIONS: dict[str, Any] = {
    "total_sales": TOTAL_SALES,
    "total_card_sales": TOTAL_CARD_SALES,
    # Amount charged by the payment provider (square) for these payments
    "provider_payment_value": TOTAL_PROVIDER_FEE,
    # Amount we take from net payment - provider cut
    "app_payment_value": APP_FEE - TOTAL_PROVIDER_FEE,
    "society_transfer_value": TOTAL_CARD_SALES - APP_FEE,
    "society_revenue": TOTAL_SALES - APP_FEE,
}
