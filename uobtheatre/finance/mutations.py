import graphene

from uobtheatre.finance.models import FinancialTransfer
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    GQLException,
    SafeMutation,
)
from uobtheatre.utils.schema import AuthRequiredMixin, IdInputField

from ..societies.models import Society
from .schema import FinancialTransferNode


class RecordFinancialTransfer(AuthRequiredMixin, SafeMutation):
    """Record a transfer of funds from the site operator to a society"""

    transfer = graphene.Field(FinancialTransferNode)

    class Arguments:
        society_id = IdInputField(required=True)
        value = graphene.Int(required=True)
        method = graphene.Argument(
            graphene.Enum("TransferMethodEnum", FinancialTransfer.Method.choices),
            required=True,
        )
        reason = graphene.String(required=False)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        if not info.context.user.has_perm("finance.create_transfer"):
            raise AuthorizationException

    @classmethod
    def resolve_mutation(cls, _, info, society_id, value, method, reason=None):
        # Find the subject
        society = Society.objects.get(pk=society_id)

        # Create the transfer
        transfer = FinancialTransfer.objects.create(
            value=value,
            method=method,
            society=society,
            user=info.context.user,
            reason=reason,
        )
        return RecordFinancialTransfer(transfer=transfer)


class Mutation(graphene.ObjectType):
    record_financial_transfer = RecordFinancialTransfer.Field()
