from uobtheatre.utils.tasks import BaseTask
from uobtheatre.payments.exceptions import CantBeRefundedException
from django.contrib.contenttypes.models import ContentType
from config.celery import app

class RefundTask(BaseTask):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if isinstance(exc, CantBeRefundedException):
            self.update_state(state="SKIPPED")
        else:
            super().on_failure(exec, task_id, args, kwargs, einfo)


@app.task(base=RefundTask, throws=(CantBeRefundedException,))
def refund_payment(payment_pk: int):
    from uobtheatre.payments.models import Transaction

    payment = Transaction.objects.get(pk=payment_pk)
    payment.refund()


@app.task(base=RefundTask, throws=(CantBeRefundedException,))
def refund_payable(
    payable_id: int, payable_content_type_id: int, authorizing_user_id: int
):
    from uobtheatre.payments.payables import Payable

    PayableModel = ContentType.objects.get(pk=payable_content_type_id).model_class()
    payable = PayableModel.objects.get(pk=payable_id)
    assert isinstance(payable, Payable)

    from uobtheatre.users.models import User

    authorizing_user = User.objects.get(pk=authorizing_user_id)
    payable.refund(authorizing_user, send_admin_email=False)


