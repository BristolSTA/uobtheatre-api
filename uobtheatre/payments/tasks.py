import abc

from django.contrib.contenttypes.models import ContentType

from config.celery import app
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.utils.tasks import BaseTask


class RefundTask(BaseTask, abc.ABC):
    """Base task for tasks that refund things"""

    def on_failure(
        self, exc, task_id, args, kwargs, einfo
    ):  # pylint: disable=too-many-arguments
        if isinstance(exc, CantBeRefundedException):
            self.update_state(state="SKIPPED", meta={"message": exc.message})
        else:
            super().on_failure(exc, task_id, args, kwargs, einfo)


@app.task(base=RefundTask, throws=(CantBeRefundedException,))
def refund_payment(payment_pk: int):
    from uobtheatre.payments.models import Transaction

    payment = Transaction.objects.get(pk=payment_pk)
    payment.refund()


@app.task(base=RefundTask, throws=(CantBeRefundedException,))
def refund_payable(
    payable_id: int, payable_content_type_id: int, authorizing_user_id
):
    """Refund a payable object automatically"""
    from uobtheatre.payments.payables import Payable

    PayableModel = ContentType.objects.get(  # pylint: disable=invalid-name
        pk=payable_content_type_id
    ).model_class()
    if not PayableModel:
        raise ValueError(
            f"No matching model exists for specified content type (Type ID: {payable_content_type_id})"
        )
    payable = PayableModel.objects.get(pk=payable_id) # type: ignore[attr-defined]
    if not isinstance(payable, Payable):
        raise ValueError(
            f"Object found, but object is not a payable object ({payable.__class__.__name__})"
        )
    from uobtheatre.users.models import User

    authorizing_user = User.objects.get(pk=authorizing_user_id)
    payable.refund(authorizing_user, send_admin_email=False)
