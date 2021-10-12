import graphene

from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import SquarePOS
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    GQLException,
    SafeMutation,
)
from uobtheatre.utils.schema import AuthRequiredMixin, IdInputField


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
        payment = Payment.objects.get(id=payment_id)
        if payment.status == Payment.PaymentStatus.COMPLETED:
            raise GQLException("A completed payment cannot be canceled.", code=400)

        # If you are not the creator of the payment's payobject
        if not payment.pay_object.creator == info.context.user:
            raise AuthorizationException(
                "You do not have permission to cancel this payment."
            )

        # If a payment that is not a SquarePOS payment is trying to be canceled
        if not payment.provider == SquarePOS.name:
            raise GQLException("This payment method cannot be canceled.", code=400)

        SquarePOS.cancel_checkout(payment.id)
        return CancelPayment()


class Mutation(graphene.ObjectType):
    cancel_payment = CancelPayment.Field()
