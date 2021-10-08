import abc

from django.contrib.contenttypes.fields import GenericRelation

from uobtheatre.payments.models import Payment
from uobtheatre.utils.models import AbstractModelMeta


class Payable(metaclass=AbstractModelMeta):
    """
    An model which can be paid for
    """

    payments = GenericRelation(
        Payment, object_id_field="pay_object_id", content_type_field="pay_object_type"
    )

    @property
    @abc.abstractmethod
    def payment_reference_id(self):
        """The id of the payable object provided to payment providers."""
        raise NotImplementedError

    @property
    def total_sales(self) -> int:
        """The amount paid by the user for this object."""
        return self.payments.annotate_sales_breakdown(["total_sales"])[  # type: ignore
            "total_sales"
        ]

    @property
    def provider_payment_value(self) -> int:
        """The amount taken by the payment provider in paying for this object."""
        return self.payments.annotate_sales_breakdown(["provider_payment_value"])[  # type: ignore
            "provider_payment_value"
        ]

    @property
    def app_payment_value(self) -> int:
        """The amount taken by us in paying for this object."""
        return self.payments.annotate_sales_breakdown(["app_payment_value"])[  # type: ignore
            "app_payment_value"
        ]

    @property
    def society_revenue(self) -> int:
        """The revenue for the society for selling this object."""
        return self.payments.annotate_sales_breakdown(["society_revenue"])[  # type: ignore
            "society_revenue"
        ]

    @property
    def society_transfer_value(self) -> int:
        """The amount of money to transfere to the society for object."""
        return self.payments.annotate_sales_breakdown(["society_transfer_value"])[  # type: ignore
            "society_transfer_value"
        ]
