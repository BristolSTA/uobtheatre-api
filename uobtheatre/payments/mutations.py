import graphene

from uobtheatre.payments.models import FinancialTransfer, Transaction
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    GQLException,
    SafeMutation,
)
from uobtheatre.utils.schema import AuthRequiredMixin, IdInputField

from ..societies.models import Society
from .schema import FinancialTransferNode


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


class RecordFinancialTransfer(AuthRequiredMixin, SafeMutation):
    """Record a transfer of funds from the site operator to a society"""

    transfer = graphene.Field(FinancialTransferNode)

    class Arguments:
        society_id = IdInputField(required=True)
        value = graphene.Int()
        method = graphene.Argument(
            graphene.Enum("TransferMethodEnum", FinancialTransfer.Method.choices)
        )

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        if not info.context.user.has_perm("payments.create_transfer"):
            raise AuthorizationException

    @classmethod
    def resolve_mutation(cls, _, info, society_id, value, method):
        # Find the subject
        society = Society.objects.get(pk=society_id)

        # Create the transfer
        transfer = FinancialTransfer.objects.create(
            value=value, method=method, society=society, user=info.context.user
        )
        return RecordFinancialTransfer(transfer=transfer)


class Mutation(graphene.ObjectType):
    cancel_payment = CancelPayment.Field()
    record_financial_transfer = RecordFinancialTransfer.Field()
