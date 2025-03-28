import abc
import math
from typing import TYPE_CHECKING, Optional

from django.contrib.contenttypes.fields import GenericRelation
from django.core.mail import mail_admins
from django.db import models
from django.db.models import Count, Q, Sum
from django.db.models.functions.comparison import Coalesce
from django.db.models.query import QuerySet
from django_celery_results.models import TaskResult

from uobtheatre.payments.emails import payable_refund_initiated_email
from uobtheatre.payments.exceptions import (
    CantBePaidForException,
    CantBeRefundedException,
)
from uobtheatre.payments.models import SalesBreakdown, Transaction
from uobtheatre.payments.tasks import refund_payable
from uobtheatre.users.models import User
from uobtheatre.utils.filters import filter_passes_on_model
from uobtheatre.utils.models import BaseModel

if TYPE_CHECKING:
    from uobtheatre.payments.transaction_providers import PaymentProvider


class PayableQuerySet(QuerySet):
    """Base queryset for payable objects"""

    def annotate_transaction_count(self) -> QuerySet:
        return self.annotate(transaction_count=Count("transactions"))

    def annotate_transaction_value(self) -> QuerySet:
        return self.annotate(transaction_totals=Coalesce(Sum("transactions__value"), 0))

    def locked(self) -> QuerySet:
        """A payable is locked if it has any pending transactions"""
        return self.filter(transactions__status=Transaction.Status.PENDING)

    def refunded(self, bool_val=True) -> QuerySet:
        """
        A payable is refunded if the value of all the payments for the pay
        object are equal to the value of all the refunds and all payments are
        completed.
        """
        qs = self.annotate_transaction_count().annotate_transaction_value()  # type: ignore
        filter_query = Q(transaction_totals=0, transaction_count__gt=1)
        if bool_val:
            return qs.filter(filter_query)
        return qs.exclude(filter_query)


PayableManager = models.Manager.from_queryset(PayableQuerySet)


# pylint: disable=too-many-public-methods
class Payable(BaseModel):  # type: ignore
    """
    An model which can be paid for
    """

    transactions = GenericRelation(
        Transaction,
        object_id_field="pay_object_id",
        content_type_field="pay_object_type",
    )

    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        CANCELLED = "CANCELLED", "Cancelled"
        PAID = "PAID", "Paid"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")

    # Stores who created the booking
    # For regular bookings this will be the user
    # For boxoffice bookings it will be the logged in boxoffice user
    # For admin bookings it will be the logged in admin
    creator = models.ForeignKey(
        User, on_delete=models.RESTRICT, related_name="created_bookings"
    )

    objects = PayableManager()

    @property
    @abc.abstractmethod
    def display_name(self):
        """Return a publically displayable name that represents this payable"""

    @property
    @abc.abstractmethod
    def payment_reference_id(self):
        """The id of the payable object provided to payment providers."""
        raise NotImplementedError

    @property
    def is_refunded(self) -> bool:
        return not self.is_locked and filter_passes_on_model(
            self, lambda qs: qs.refunded()  # type: ignore
        )

    @property
    def is_locked(self) -> bool:
        return filter_passes_on_model(self, lambda qs: qs.locked())  # type: ignore

    @property
    def can_be_refunded(self):
        return self.validate_cant_be_refunded() is None

    def validate_cant_be_refunded(self) -> Optional[CantBeRefundedException]:
        """Validates if the booking can't be refunded. If it can't, it returns an exception. If it can, it returns None"""
        if self.status not in [self.Status.PAID, self.Status.CANCELLED]:
            return CantBeRefundedException(
                f"{self.__class__.__name__} ({self}) can't be refunded due to it's status ({self.status})"
            )
        if self.transactions.payments().count() == 0:  # type: ignore
            return CantBeRefundedException(
                f"{self.__class__.__name__} ({self}) can't be refunded because it has no payments"
            )
        if self.is_refunded:
            return CantBeRefundedException(
                f"{self.__class__.__name__} ({self}) can't be refunded because is already refunded"
            )
        if self.is_locked:
            return CantBeRefundedException(
                f"{self.__class__.__name__} ({self}) can't be refunded because it is locked"
            )
        return None

    def async_refund(
        self,
        authorizing_user: User,
        preserve_provider_fees: bool = True,
        preserve_app_fees: bool = False,
    ):
        """
        Create "refund_payable" task to refund all the payments for the
        payable. This tasks calls the refund method with `do_async` to queue a
        refund tasks for each payment.
        """
        refund_payable.delay(
            self.pk,
            self.content_type.pk,
            authorizing_user.pk,
            preserve_provider_fees,
            preserve_app_fees,
        )

    def refund(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        authorizing_user: User,
        do_async=True,
        send_admin_email=True,
        preserve_provider_fees=True,
        preserve_app_fees=False,
    ):
        """
        Refund the all the payments in the payable.

        Args:
            authorizing_user (User): The user authorizing the refund
            do_async (bool): If true a task is queued to refund each payment.
                Otherwise payments are refunded synchronously.
            send_admin_email (bool): If true send an email to the admins after the
                refunds are created/queued.
            preserve_provider_fees (bool): If true the refund is reduced by the amount required to cover the payment's provider_fee
                i.e. the refund is reduced by the amount required to cover only Square's fees.
                If both preserve_provider_fees and preserve_app_fees are true, the refund is reduced by the larger of the two fees.
            preserve_app_fees (bool): If true the refund is reduced by the amount required to cover the payment's app_fee
                i.e. the refund is reduced by the amount required to cover our fees (the various misc_costs, such as the theatre improvement levy).
                If both preserve_provider_fees and preserve_app_fees are true, the refund is reduced by the larger of the two fees.
        """
        if error := self.validate_cant_be_refunded():  # type: ignore
            raise error  # pylint: disable=raising-bad-type

        for payment in self.transactions.filter(type=Transaction.Type.PAYMENT).all():  # type: ignore
            (
                payment.async_refund()
                if do_async
                else payment.refund(preserve_provider_fees, preserve_app_fees)
            )

        if send_admin_email:
            mail = payable_refund_initiated_email(authorizing_user, [self])
            mail_admins(
                f"{self.__class__.__name__} Refunds Initiated",
                mail.to_plain_text(),
                html_message=mail.to_html(),
            )

    @property
    def total(self) -> int:
        """The total cost of the payable in pence.

        The final price of the payable with all dicounts and misc costs
        applied. This is the price the User will be charged.

        Returns:
            (int): total price of the payable in penies
        """
        # If the subtotal is 0 then do not apply the misc costs
        return math.ceil(self.subtotal + self.misc_costs_value) if self.subtotal else 0

    @property
    @abc.abstractmethod
    def subtotal(self) -> int:
        """Price of the payable with discounts applied.

        Returns the subtotal of the payable. This is the total value including
        single and group discounts before any misc costs are applied. If an
        admin discount is also applied this will be added here.

        Returns:
            int: price of the payable with discounts applied in penies
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def misc_costs_value(self):
        """The total platform fee, in pence, for this payable"""
        raise NotImplementedError

    def pay(self, payment_method: "PaymentProvider") -> Optional["Transaction"]:
        """
        Pay for payable using provided payment method.

        Args:
            payment_method (PaymentMethod): The payment method used to pay for
                the payable

        Returns:
            Payment: The payment created by the checkout (optional)

        Raises:
            CantBePaidForException: If the status of the payable is not
                IN_PROGRESS
        """
        if self.status != Payable.Status.IN_PROGRESS:
            raise CantBePaidForException(
                message=f"A payable with status {self.get_status_display()} cannot be paid for"
            )

        # Cancel and delete pending payments for this booking
        for payment in self.transactions.filter(status=Transaction.Status.PENDING):  # type: ignore
            payment.cancel()

        payment = payment_method.pay(self.total, self.misc_costs_value, self)

        # If a payment is created set the booking as paid
        if payment.status == Transaction.Status.COMPLETED:
            self.complete(payment)

        return payment

    def complete(
        self, payment: Optional[Transaction] = None
    ):  # pylint: disable=unused-argument
        """
        Called once the pay object has been completly paid for. Payment passed
        is the finishing transaction
        """
        self.status = Payable.Status.PAID
        self.save()

    @property
    def sales_breakdown(self) -> SalesBreakdown:
        return SalesBreakdown(self.transactions)  # type: ignore

    @property
    def associated_tasks(self):
        """Get tasks associated with this payable"""
        payable_tasks = TaskResult.objects.filter(
            task_name="uobtheatre.payments.tasks.refund_payable",
            task_args__iregex=f"\({self.pk}, {self.content_type.pk}",  # pylint: disable=anomalous-backslash-in-string
        )
        payment_tasks = self.transactions.associated_tasks()
        return payable_tasks | payment_tasks

    class Meta:
        abstract = True
