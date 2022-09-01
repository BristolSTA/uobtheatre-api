import graphene

from uobtheatre.payments.models import Transaction, Transfer
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    GQLException,
    SafeMutation,
)
from uobtheatre.utils.schema import AuthRequiredMixin, IdInputField

from ..societies.models import Society
from ..utils.validators import ValidationError
from .schema import TransferNode


class CancelPayment(AuthRequiredMixin, SafeMutation):
    """Cancel a payment

    This is used to cancel PENDING payments. Currently this is only for
    SquarePOS payments.

    Args:
        payment_id (str): The id of the payment to cancel.
    """

    class Arguments:
        payment_id = IdInputField(required=True)

    @classmethod
    def resolve_mutation(cls, _, info, payment_id):
        payment = Transaction.objects.get(id=payment_id)
        if not payment.status == Transaction.Status.PENDING:
            raise GQLException(
                "A payment must be in progress to be canceled.",
                code=400,
            )

        # If you are not the creator of the payment's payobject
        if not payment.pay_object.creator == info.context.user:
            raise AuthorizationException(
                "You do not have permission to cancel this payment."
            )

        payment.cancel()
        return CancelPayment()


class RecordTransfer(AuthRequiredMixin, SafeMutation):
    """Record a transfer of funds from the site operator to a subject (society)"""

    transfer = graphene.Field(TransferNode)

    class Arguments:
        subject_id = IdInputField(required=True)
        subject_type = graphene.Argument(
            graphene.Enum("SubjectType", [("SOCIETY", "SOCIETY")])
        )
        value = graphene.Int()
        method = graphene.Argument(
            graphene.Enum("TransferMethodEnum", Transfer.Method.choices)
        )

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        if not info.context.user.has_perm("payments.create_transfer"):
            raise AuthorizationException

    @classmethod
    def resolve_mutation(cls, _, info, subject_id, subject_type, value, method):
        # Find the subject
        subject = None

        if subject_type == "SOCIETY":
            subject = Society.objects.get(pk=subject_id)

        if not subject:
            raise ValidationError(f"A subject with ID {subject_id} was not found")

        # Create the transfer
        transfer = Transfer.objects.create(
            value=value, method=method, subject=subject, user=info.context.user
        )
        return RecordTransfer(transfer=transfer)


class Mutation(graphene.ObjectType):
    cancel_payment = CancelPayment.Field()
    record_transfer = RecordTransfer.Field()
