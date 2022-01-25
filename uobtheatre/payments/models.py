from typing import TYPE_CHECKING, Any

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, Sum
from django.db.models.enums import TextChoices
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet
from django_celery_results.models import TaskResult

from uobtheatre.mail.composer import MailComposer
from uobtheatre.payments import transaction_providers
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.tasks import refund_payment
from uobtheatre.payments.transaction_providers import (
    Cash,
    PaymentProvider,
    RefundProvider,
    TransactionProvider,
)
from uobtheatre.utils.models import BaseModel, TimeStampedMixin

if TYPE_CHECKING:
    from uobtheatre.payments.payables import Payable


class TransactionQuerySet(QuerySet):
    """The query set for payments"""

    def annotate_sales_breakdown(self, breakdowns: list[str] = None):
        """Annotate sales breakdown onto payments"""
        annotations = {
            k: Coalesce(v, 0)
            for k, v in SALE_BREAKDOWN_ANNOTATIONS.items()
            if breakdowns is None or k in breakdowns
        }
        return self.aggregate(**annotations)

    def payments(self):
        return self.filter(type=Transaction.Type.PAYMENT)

    def refunds(self):
        return self.filter(type=Transaction.Type.REFUND)

    def missing_provider_fee(self):
        return self.filter(provider_fee=None)

    def sync(self):
        """
        Sync all (non manual) payments with their providers. Currently the only
        syncing we do is for the processing fee.
        """
        for payment in self:
            payment.sync_transaction_with_provider()

    def associated_tasks(self):
        """
        Return a queryset of tasks associated with these transactions
        """
        pks = self.values_list("pk", flat=True)
        pks_regex = "|".join(map(str, pks))
        return TaskResult.objects.filter(
            task_name="uobtheatre.payments.tasks.refund_payment",
            task_args__iregex=f"\(({pks_regex}), {self.model.content_type.pk},",  # pylint: disable=anomalous-backslash-in-string
        )


class Transaction(TimeStampedMixin, BaseModel):

    """The model for a transaction.

    When ever a transaction is made for a Production a Payment object is
    created. This stores the key information about the transaction.
    """

    class Type(models.TextChoices):
        """Whether the payment was a refund or purchase."""

        PAYMENT = "PAYMENT", "Payment"
        REFUND = "REFUND", "Refund"

    class Status(models.TextChoices):
        """The status of the payment."""

        PENDING = "PENDING", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

        @classmethod
        def from_square_status(cls, square_status: str):
            """Convert a Square payment status to a PaymentStatus"""
            status_map = {
                "APPROVED": cls.PENDING,
                "PENDING": cls.PENDING,
                "COMPLETED": cls.COMPLETED,
                "REJECTED": cls.FAILED,
                "CANCELLED": cls.FAILED,
                "FAILED": cls.FAILED,
            }
            return status_map[square_status]

    objects = TransactionQuerySet.as_manager()

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
    pay_object: "Payable" = GenericForeignKey(
        "pay_object_type", "pay_object_id"
    )  # type: ignore

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.PAYMENT,
    )
    status: TextChoices = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )  # type: ignore

    provider_transaction_id = models.CharField(max_length=128, null=True, blank=True)
    provider_name = models.CharField(
        max_length=20, choices=transaction_providers.TransactionProvider.choices  # type: ignore
    )

    value = models.IntegerField()
    currency = models.CharField(max_length=10, default="GBP")

    card_brand = models.CharField(max_length=20, null=True, blank=True)
    last_4 = models.CharField(max_length=4, null=True, blank=True)

    # Amount charged by payment provider in GBP
    provider_fee = models.IntegerField(null=True, blank=True)
    # Amount charged by us to process payment
    app_fee = models.IntegerField(null=True, blank=True)

    @property
    def is_refunded(self) -> bool:
        """
        A payment is refunded if the value of all the payments for the pay
        object are equal to the value of all the refunds and all payments are
        completed.
        """
        return self.pay_object.is_refunded

    @property
    def provider(self):
        return next(
            method
            for method in list(TransactionProvider.__all__)
            if method.name == self.provider_name
        )

    def url(self):
        """Payment provider transaction link.

        Returns:
            string, optional: url to provider's payment reference
        """
        if self.provider_name == transaction_providers.SquareOnline.name:
            return f"https://squareupsandbox.com/dashboard/sales/transactions/{self.provider_transaction_id}"
        return None

    @property
    def value_currency(self):
        return f"{(abs(self.value) / 100):.2f} {self.currency}"

    def sync_transaction_with_provider(self, data=None):
        """Sync the payment with the provider payment"""
        self.provider.sync_transaction(self, data)

    def notify_user(self):
        """Notifies the owner of the transaction of the current status of this transaction. Currently used only for refunds"""
        user = self.pay_object.user
        if (
            self.type == Transaction.Type.REFUND
            and self.status == Transaction.Status.COMPLETED
        ):
            MailComposer().greeting(user).line(
                f"Your payment of {self.value_currency} for {self.pay_object.display_name} has been successfully refunded. (ID: {self.provider_transaction_id} | {self.id})."
            ).line(
                "This will have been refunded to your original payment method."
            ).send(
                "Refund successfully processed", user.email
            )
            return

    def cancel(self):
        """
        Cancel payment

        This is currently only possible for SquarePOS payments that are
        pending.
        """
        if self.status == Transaction.Status.PENDING:
            self.provider.cancel(self)
            self.delete()

    def can_be_refunded(self, refund_provider=None, raises=False):
        """If the payment can be refunded either automatically or manually"""
        if self.type != Transaction.Type.PAYMENT:
            if raises:
                raise CantBeRefundedException(
                    f"A {self.type.label.lower()} can't be refunded"
                )
            return False

        if self.status != Transaction.Status.COMPLETED:
            if raises:
                raise CantBeRefundedException(
                    f"A {self.status.label.lower()} payment can't be refunded"
                )
            return False

        if not self.provider.is_refundable:
            if raises:
                raise CantBeRefundedException(
                    f"A {self.provider_name} payment can't be refunded"
                )
            return False

        # Check that the refund provider (if supplied) is valid for the original provider
        if refund_provider is not None and not self.provider.is_valid_refund_provider(
            refund_provider
        ):
            if raises:
                raise CantBeRefundedException(
                    f"Cannot use refund provider {refund_provider.name} with a {self.provider.name} payment"
                )
            return False

        return True

    def async_refund(self):
        refund_payment.delay(self.pk)

    def refund(self, refund_provider: RefundProvider = None):
        """Refund the payment"""
        self.can_be_refunded(refund_provider=refund_provider, raises=True)

        if refund_provider is None:
            # If no provider is provided, use the auto refund provider
            if not (refund_provider := self.provider.automatic_refund_provider):
                raise CantBeRefundedException(
                    f"A {self.provider_name} payment cannot be automatically refunded"
                )

        refund_provider.refund(self)


TOTAL_PROVIDER_FEE = Coalesce(
    Sum(
        "provider_fee",
    ),
    0,
)
NET_TOTAL = Sum("value")
NET_CARD_TOTAL = Sum("value", filter=(~Q(provider_name=Cash.name)))
TOTAL_SALES = Sum("value", filter=Q(type=Transaction.Type.PAYMENT))
TOTAL_CARD_SALES = Sum(
    "value", filter=(~Q(provider_name=Cash.name) & Q(type=Transaction.Type.PAYMENT))
)
TOTAL_REFUNDS = Sum("value", filter=Q(type=Transaction.Type.REFUND))
TOTAL_CARD_REFUNDS = Sum(
    "value", filter=(~Q(provider_name=Cash.name) & Q(type=Transaction.Type.REFUND))
)
APP_FEE = Coalesce(Sum("app_fee"), 0)

SALE_BREAKDOWN_ANNOTATIONS: dict[str, Any] = {
    # Gross Income
    "net_income": NET_TOTAL,
    "net_card_income": NET_CARD_TOTAL,
    # Total Purchases / Sales
    "total_sales": TOTAL_SALES,
    "total_card_sales": TOTAL_CARD_SALES,
    # Total Refunds
    "total_refunds": TOTAL_REFUNDS,
    "total_card_refunds": TOTAL_CARD_REFUNDS,
    # Gross Amount charged by the payment provider (square) for these payments
    "provider_payment_value": TOTAL_PROVIDER_FEE,
    # Amount we take from net payment - provider cut
    "app_payment_value": APP_FEE - TOTAL_PROVIDER_FEE,
    "society_transfer_value": NET_CARD_TOTAL - APP_FEE,
    "society_revenue": NET_TOTAL - APP_FEE,
}
