from typing import Union
from uuid import UUID

from django.core.mail import mail_admins

from config.celery import app
from uobtheatre.payments.tasks import RefundTask


@app.task(base=RefundTask)
def refund_performance(
    performance_id: int,
    authorizing_user_id,
    preserve_provider_fees: bool = True,
    preserve_app_fees: bool = False,
):
    """Refund the performance's bookings
    Args:
        performance_id (int): The id of the performance to refund
        authorizing_user_id (int): Id of the user authorizing the refund
        preserve_provider_fees (bool): If true the refund is reduced by the amount required to cover the payment's provider_fee
            i.e. the refund is reduced by the amount required to cover only Square's fees.
            If both preserve_provider_fees and preserve_app_fees are true, the refund is reduced by the larger of the two fees.
        preserve_app_fees (bool): If true the refund is reduced by the amount required to cover the payment's app_fee
            i.e. the refund is reduced by the amount required to cover our fees (the various misc_costs, such as the theatre improvement levy).
            If both preserve_provider_fees and preserve_app_fees are true, the refund is reduced by the larger of the two fees.
    Raises:
        CantBeRefundedException: Raised if the performance can't be refunded
    """
    from uobtheatre.payments.payables import Payable
    from uobtheatre.productions.emails import performances_refunded_email
    from uobtheatre.productions.models import Performance
    from uobtheatre.users.models import User

    performance = Performance.objects.get(pk=performance_id)
    authorizing_user = User.objects.get(pk=authorizing_user_id)

    for booking in performance.bookings.filter(status=Payable.Status.PAID):
        booking.async_refund(
            authorizing_user=authorizing_user,
            preserve_provider_fees=preserve_provider_fees,
            preserve_app_fees=preserve_app_fees,
        )

    mail = performances_refunded_email(
        authorizing_user,
        [performance],
    )
    mail_admins(
        "Performance Refunds Initiated",
        mail.to_plain_text(),
        html_message=mail.to_html(),
    )
