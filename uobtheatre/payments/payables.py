import abc

from django.contrib.contenttypes.fields import GenericRelation
from django.db.models import Sum

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
        """
        The id of the payable object provided to payment providers.
        """
        raise NotImplementedError

    @property
    def provider_payment_value(self) -> int:
        """The amount taken by the payment provider in paying for this object."""
        return self.payments.filter(type=Payment.PaymentType.PURCHASE).aggregate(  # type: ignore
            value=Sum("provider_fee")
        )[
            "value"
        ]

    @property
    def app_payment_value(self) -> int:
        """The amount taken by us in paying for this object."""
        return self.payments.filter(type=Payment.PaymentType.PURCHASE).aggregate(  # type: ignore
            value=Sum("app_fee") - Sum("provider_fee")
        )[
            "value"
        ]

    @property
    def society_payment_value(self) -> int:
        """The amount owed to the society for selling this object."""
        return self.payments.filter(type=Payment.PaymentType.PURCHASE).aggregate(  # type: ignore
            value=Sum("value") - Sum("app_fee")
        )[
            "value"
        ]
