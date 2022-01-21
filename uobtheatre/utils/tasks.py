from typing import TYPE_CHECKING

from celery import Task
from django.contrib.contenttypes.models import ContentType
from django.core.mail import mail_admins
from sentry_sdk import capture_exception

from config.celery import app
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.payables import Payable
from uobtheatre.productions.emails import performances_refunded_email

if TYPE_CHECKING:
    pass

# Tasks
class BaseTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        capture_exception(exc)
        super().on_failure(exec, task_id, args, kwargs, einfo)


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
    PayableModel = ContentType.objects.get(pk=payable_content_type_id)
    payable = PayableModel.objects.get(pk=payable_id)
    assert isinstance(payable, Payable)

    from uobtheatre.users.models import User

    authorizing_user = User.objects.get(pk=authorizing_user_id)

    payable.refund(authorizing_user, send_admin_email=False)


@app.task(base=RefundTask)
def refund_performance(performance_id: int, authorizing_user_id: int):
    """Refund the performance's bookings
    Args:
        authorizing_user (User): The user authorizing the refund
        send_admin_email (bool, optional): Wether to authorize the refund. Defaults to True.
    Raises:
        CantBeRefundedException: Raised if the performance can't be refunded
    """
    from uobtheatre.payments.payables import Payable
    from uobtheatre.productions.models import Performance
    from uobtheatre.users.models import User

    performance = Performance.objects.get(pk=performance_id)
    authorizing_user = User.objects.get(pk=authorizing_user_id)

    for booking in performance.bookings.filter(status=Payable.Status.PAID):
        booking.async_refund(authorizing_user=authorizing_user)

    mail = performances_refunded_email(
        authorizing_user,
        [performance],
    )
    mail_admins(
        "Performance Refunds Initiated",
        mail.to_plain_text(),
        html_message=mail.to_html(),
    )
