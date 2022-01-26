from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable


@receiver(pre_save, sender=Transaction)
def pre_transaction_save(instance: Transaction, **_):
    pre_transaction_save_callback(instance)


@receiver(post_save, sender=Transaction)
def post_transaction_save(instance: Transaction, **_):
    post_transaction_save_callback(instance)


def pre_transaction_save_callback(transaction_instance: Transaction):
    """Pre save payment actions"""
    old_instance = (
        Transaction.objects.get(pk=transaction_instance.id)
        if transaction_instance.id
        and not transaction_instance._state.adding  # pylint: disable=protected-access
        else None
    )

    if not old_instance:
        return

    if (
        transaction_instance.type == Transaction.Type.REFUND
        and transaction_instance.status == Transaction.Status.COMPLETED
        and not old_instance.status == Transaction.Status.COMPLETED
    ):
        # This refund transaction has now been completed. Notify the payment owner
        transaction_instance.notify_user()


def post_transaction_save_callback(transaction_instance: Transaction):
    """Post save payment actions"""
    # If the object is refunded and not locked, set it to cancelled
    if (
        not transaction_instance.Status == Payable.Status.CANCELLED
        and not transaction_instance.pay_object.is_locked
        and transaction_instance.pay_object.is_refunded
    ):
        transaction_instance.pay_object.status = Payable.Status.CANCELLED
        transaction_instance.pay_object.save()
