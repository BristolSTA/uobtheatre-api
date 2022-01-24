from django.core.mail import mail_admins

from uobtheatre.payments.tasks import RefundTask
from config.celery import app

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
    from uobtheatre.productions.emails import performances_refunded_email


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
