from enum import Enum
from typing import TYPE_CHECKING, Optional

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
from uobtheatre.payments.exceptions import (
    CantBeCanceledException,
    CantBeRefundedException,
)
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

    def annotate_sales_breakdown(
        self, breakdowns: Optional[list["SalesBreakdown.Enums"]] = None
    ):
        """Annotate sales breakdown onto payments"""
        annotations = {
            breakdown.key: Coalesce(breakdown.value, 0)
            for breakdown in SalesBreakdown.Enums
            if breakdowns is None or breakdown in breakdowns
        }
        return self.aggregate(**annotations)

    def get_sales_breakdown(self, breakdown: "SalesBreakdown.Enums"):
        # NOTE: Calling aggregate on an empty queryset gives None so the
        # Coalesce is not applied this fix works here but still an
        # issue/feature above
        return self.annotate_sales_breakdown(breakdowns=[breakdown])[breakdown.key] or 0

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
            task_args__iregex=f"\(({pks_regex}),\)",  # pylint: disable=anomalous-backslash-in-string
        )


TransactionManager = models.Manager.from_queryset(TransactionQuerySet)


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
                "IN_PROGRESS": cls.PENDING,
                "CANCEL_REQUESTED": cls.PENDING,
                "COMPLETED": cls.COMPLETED,
                "REJECTED": cls.FAILED,
                "CANCELED": cls.FAILED,
                "FAILED": cls.FAILED,
            }
            return status_map[square_status]

    objects = TransactionManager()

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

    type: TextChoices = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.PAYMENT,
    )  # type: ignore
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
            for method in list(  # type: ignore[call-overload]
                TransactionProvider.__all__
            )
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

    def cancel(self):
        """
        Cancel payment
        """
        if self.status != self.Status.PENDING:
            raise CantBeCanceledException(
                f"A transaction of status {self.status} cannot be canceled"
            )
        self.provider.cancel(self)

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

    def async_refund(self, preserve_provider_fees=True, preserve_app_fees=False):
        """
        Create "refund_payment" task to refund the payment. The task queue the
        refund method.
        """
        refund_payment.delay(
            self.pk,
            preserve_provider_fees=preserve_provider_fees,
            preserve_app_fees=preserve_app_fees,
        )

    def refund(
        self,
        preserve_provider_fees=True,
        preserve_app_fees=False,
        refund_provider: Optional[RefundProvider] = None,
    ):
        """
        Refund the payment

        Args:
            preserve_provider_fees (bool): If true the refund is reduced by the amount required to cover the payment's provider_fee
                i.e. the refund is reduced by the amount required to cover only Square's fees.
                If both preserve_provider_fees and preserve_app_fees are true, the refund is reduced by the larger of the two fees.
            preserve_app_fees (bool): If true the refund is reduced by the amount required to cover the payment's app_fee
                i.e. the refund is reduced by the amount required to cover our fees (the various misc_costs, such as the theatre improvement levy).
                If both preserve_provider_fees and preserve_app_fees are true, the refund is reduced by the larger of the two fees.
            refund_provider (RefundProvider): If a refund provider is provider,
                that is used to refund the payment. Otherwise the
                automatic_refund_provider of the payment transaction provider
                is used.

        Raises:
            CantBeRefundedException: Raised if the payment cannot be refunded
                for a known reason.
        """
        self.can_be_refunded(refund_provider=refund_provider, raises=True)

        if refund_provider is None:
            # If no provider is provided, use the auto refund provider
            if not (refund_provider := self.provider.automatic_refund_provider):
                raise CantBeRefundedException(
                    f"A {self.provider_name} payment cannot be automatically refunded"
                )

        refund_amount = None

        if (
            preserve_provider_fees
            and self.provider_fee
            and preserve_app_fees
            and self.app_fee
        ):
            refund_amount = self.value
            refund_amount -= max(
                self.provider_fee, self.app_fee
            )  # Refund minus the larger of the two fees so we protect ourselves but don't double dip
        elif preserve_provider_fees and self.provider_fee is not None:
            refund_amount = self.value
            refund_amount -= self.provider_fee
        elif preserve_app_fees and self.app_fee is not None:
            refund_amount = self.value
            refund_amount -= self.app_fee

        if refund_amount and refund_amount < 0:
            # Refund amount can't be negative
            raise CantBeRefundedException(
                "This refund would result in a negative refund amount"
            )

        refund_provider.refund(self, custom_refund_amount=refund_amount)

    class Meta:
        ordering = ["-created_at"]


class SalesBreakdown:
    """
    Class representing the sales breakdown for a given transaction query set
    """

    class Enums(Enum):
        """
        The available breakdowns.

        Each enum variant is assigned to the expression used to calculate its
        value.
        """

        PROVIDER_PAYMENT_VALUE = Coalesce(
            Sum(
                "provider_fee",
            ),
            0,
        )
        NET_TRANSACTIONS = Sum("value")
        NET_CARD_TRANSACTIONS = Sum("value", filter=~Q(provider_name=Cash.name))
        TOTAL_PAYMENTS = Sum("value", filter=Q(type=Transaction.Type.PAYMENT))
        TOTAL_CARD_PAYMENTS = Sum(
            "value",
            filter=(~Q(provider_name=Cash.name) & Q(type=Transaction.Type.PAYMENT)),
        )
        TOTAL_REFUNDS = Sum("value", filter=Q(type=Transaction.Type.REFUND))
        TOTAL_CARD_REFUNDS = Sum(
            "value",
            filter=(~Q(provider_name=Cash.name) & Q(type=Transaction.Type.REFUND)),
        )
        APP_FEE = Coalesce(Sum("app_fee"), 0)

        APP_PAYMENT_VALUE = APP_FEE - PROVIDER_PAYMENT_VALUE
        SOCIETY_TRANSFER_VALUE = NET_CARD_TRANSACTIONS - APP_FEE
        SOCIETY_REVENUE = NET_TRANSACTIONS - APP_FEE

        @property
        def key(self):
            return self.name.lower()

    def __init__(self, transaction_qs: TransactionQuerySet) -> None:
        super().__init__()
        self.transaction_qs = transaction_qs

    @property
    def total_payments(self) -> int:
        """The positive amounts paid by the user for this object.

        - This does not include refunds.
        - This does include the square fee.
        """
        return self.transaction_qs.get_sales_breakdown(self.Enums.TOTAL_PAYMENTS)

    @property
    def net_transactions(self) -> int:
        """The net amount paid by the user for this object. (This includes refunds)"""
        return self.transaction_qs.get_sales_breakdown(self.Enums.NET_TRANSACTIONS)

    @property
    def total_refunds(self) -> int:
        """The negative amounts paid by the user for this object. (i.e. money
        paid back to the user in the form of a refund)
        """
        return self.transaction_qs.get_sales_breakdown(self.Enums.TOTAL_REFUNDS)

    @property
    def provider_payment_value(self) -> int:
        """The amount taken by the payment provider in paying for this object."""
        return self.transaction_qs.get_sales_breakdown(
            self.Enums.PROVIDER_PAYMENT_VALUE
        )
    
    @property
    def app_fee(self) -> int:
        """The amount taken by us in paying for this object."""
        return self.transaction_qs.get_sales_breakdown(
            self.Enums.APP_FEE
        )

    @property
    def app_payment_value(self) -> int:
        """The amount taken by us in paying for this object."""
        return self.transaction_qs.get_sales_breakdown(self.Enums.APP_PAYMENT_VALUE)

    @property
    def society_revenue(self) -> int:
        """The revenue for the society for selling this object."""
        return self.transaction_qs.get_sales_breakdown(self.Enums.SOCIETY_REVENUE)

    @property
    def society_transfer_value(self) -> int:
        """The amount of money to transfer to the society for object."""
        return self.transaction_qs.get_sales_breakdown(
            self.Enums.SOCIETY_TRANSFER_VALUE
        )
