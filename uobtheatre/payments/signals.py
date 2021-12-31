from django.db.models.signals import post_save
from django.dispatch import receiver

from uobtheatre.mail.composer import MailComposer
from uobtheatre.payments.models import Payment
from uobtheatre.payments.payables import Payable


@receiver(post_save, sender=Payment)
def on_payment_save(instance: Payment, **_):
    on_payment_save_callback(instance)


def on_payment_save_callback(payment_instance: Payment):
    """Post payment save actions"""
    # Check if the payment has a pay object. If it does, check what the status should be
    if not payment_instance.pay_object:
        return

    # If the payobject is classed as refunded, make it so
    if (
        payment_instance.pay_object.is_refunded
        and not payment_instance.pay_object.status == Payable.PayableStatus.REFUNDED
    ):
        payment_instance.pay_object.status = Payable.PayableStatus.REFUNDED
        payment_instance.pay_object.save()

        # Notify the user
        user = payment_instance.pay_object.user
        MailComposer().line(
            f"Your payment of {payment_instance.value_currency} has been successfully refunded (ID: {payment_instance.provider_payment_id} | {payment_instance.id})."
        ).line(
            f"This will have been refunded in your original payment method ({payment_instance.provider_class.description}{f' {payment_instance.card_brand} ending {payment_instance.last_4}' if payment_instance.card_brand and payment_instance.last_4 else ''})"
        ).send(
            "Refund successfully processed", user.email
        )
        return

    # If the payment is of type refund, ensure that the pay_object is marked locked
    if payment_instance.type == Payment.PaymentType.REFUND:
        payment_instance.pay_object.status = Payable.PayableStatus.LOCKED
        payment_instance.pay_object.save()
