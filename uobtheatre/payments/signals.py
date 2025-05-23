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

    # If the transaction is a refund and the status has changed to completed, notify the user
    if (
        transaction_instance.type == Transaction.Type.REFUND
        and transaction_instance.status == Transaction.Status.COMPLETED
        and not old_instance.status == Transaction.Status.COMPLETED
    ):
        transaction_instance.notify_user()


def post_transaction_save_callback(transaction_instance: Transaction):
    """Post save payment actions"""
    # If the payable is an in-process refund and the transaction has now been completed, mark the payable as refunded
    if (
        transaction_instance.pay_object.status == Payable.Status.REFUND_PROCESSING
        and not transaction_instance.pay_object.Status == Payable.Status.REFUNDED
        and not transaction_instance.pay_object.is_locked
        and transaction_instance.pay_object.is_refunded
    ):
        transaction_instance.pay_object.status = Payable.Status.REFUNDED
        transaction_instance.pay_object.save()
