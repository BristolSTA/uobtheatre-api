from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver

from uobtheatre.payments.models import Transaction
from uobtheatre.productions.models import Production


@receiver(pre_save, sender=Production)
def pre_production_save(instance: Production, **_):
    check_production_status_validation(instance)


def check_production_status_validation(production_instance: Production):
    """Check that the production's status is valid given it's current state"""
    old_instance = (
        Production.objects.get(pk=production_instance.id)
        if production_instance.id
        and not production_instance._state.adding  # pylint: disable=protected-access
        else None
    )

    # If we are changing the status to closed
    if (
        old_instance
        and production_instance.status == Production.Status.CLOSED
        and not old_instance.status == Production.Status.CLOSED
    ):
        # Get number of performances that have payments that are not complete
        num_performances_with_uncomplete_payments = (
            production_instance.performances.filter(
                bookings__transactions__status=Transaction.Status.PENDING
            ).count()
        )
        if num_performances_with_uncomplete_payments > 0:
            raise ValidationError(
                "This production can't be closed because it has payments that are not yet complete"
            )
