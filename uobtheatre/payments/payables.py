import abc

from django.contrib.contenttypes.fields import GenericRelation
from django.core.mail import mail_admins
from django.db import models
from django.db.models import Sum
from django.db.models.functions.comparison import Coalesce
from django.db.models.query import QuerySet

from uobtheatre.payments.emails import payable_refund_initiated_email
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.models import Transaction
from uobtheatre.users.models import User
from uobtheatre.utils.filters import filter_passes_on_model
from uobtheatre.utils.models import AbstractModelMeta


class PayableQuerySet(QuerySet):
    """Base queryset for payable objects"""

    def locked(self) -> QuerySet:
        """A payable is locked if it has any pending transactions"""
        return self.filter(transactions__status=Transaction.Status.PENDING)

    def refunded(self) -> QuerySet:
        """
        A payable is refunded if the value of all the payments for the pay
        object are equal to the value of all the refunds and all payments are
        completed.
        """
        return self.annotate(
            transaction_totals=Coalesce(Sum("transactions__value"), 0)
        ).filter(transaction_totals=0)


class Payable(models.Model, metaclass=AbstractModelMeta):  # type: ignore
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

    objects = PayableQuerySet.as_manager()

    @property
    @abc.abstractmethod
    def user(self):
        raise NotImplementedError

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
        return (
            self.status in [self.Status.PAID, self.Status.CANCELLED]
            and not self.is_refunded
            and not self.is_locked
        )

    def refund(self, authorizing_user: User, send_admin_email=True):
        """Refund the payable"""
        if not self.can_be_refunded:
            raise CantBeRefundedException(
                f"{self.__class__.__name__} ({self}) cannot be refunded"
            )

        for payment in self.transactions.filter(type=Transaction.Type.PAYMENT).all():
            payment.refund()

        if send_admin_email:
            mail = payable_refund_initiated_email(authorizing_user, [self])
            mail_admins(
                f"{self.__class__.__name__} Refunds Initiated",
                mail.to_plain_text(),
                html_message=mail.to_html(),
            )

    def complete(self, payment: Transaction = None):
        """
        Called once the pay object has been completly paid for. Payment passed is the finishing transaction
        """

    @property
    def total_sales(self) -> int:
        """The amount paid by the user for this object."""
        return self.transactions.annotate_sales_breakdown(["total_sales"])[  # type: ignore
            "total_sales"
        ]

    @property
    def provider_payment_value(self) -> int:
        """The amount taken by the payment provider in paying for this object."""
        return self.transactions.annotate_sales_breakdown(["provider_payment_value"])[  # type: ignore
            "provider_payment_value"
        ]

    @property
    def app_payment_value(self) -> int:
        """The amount taken by us in paying for this object."""
        return self.transactions.annotate_sales_breakdown(["app_payment_value"])[  # type: ignore
            "app_payment_value"
        ]

    @property
    def society_revenue(self) -> int:
        """The revenue for the society for selling this object."""
        return self.transactions.annotate_sales_breakdown(["society_revenue"])[  # type: ignore
            "society_revenue"
        ]

    @property
    def society_transfer_value(self) -> int:
        """The amount of money to transfere to the society for object."""
        return self.transactions.annotate_sales_breakdown(["society_transfer_value"])[  # type: ignore
            "society_transfer_value"
        ]

    class Meta:
        abstract = True
