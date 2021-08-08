from datetime import datetime
from typing import List

from uobtheatre.payments.models import Payment


class ObjectTotal:
    def __init__(self, subject_object: object, total: int) -> None:
        self.object = subject_object
        self.total = total


class ObjectTotalCollection:
    """A wrapper around a collection of ObjectTotals"""

    def __init__(self) -> None:
        self.collection: List[ObjectTotal] = []

    def merge_push(self, object_total: ObjectTotal):
        """Pushes an object total into the collection if a similar object doesn't already exisit. Otherwise, adds the total to the exisiting total"""
        match = next(
            (total for total in self.collection if total.object == object_total.object),
            None,
        )
        if match:
            match.total += object_total.total
        else:
            self.collection.append(object_total)


class ProviderPeriodTotals:
    """Generates a report on payments made via specified providers over a given time period"""

    def __init__(self, start: datetime, end: datetime, providers: List) -> None:
        self.production_totals = ObjectTotalCollection()
        self.society_totals = ObjectTotalCollection()
        self.provider_totals = ObjectTotalCollection()
        self.matched_payments = (
            Payment.objects.filter(created_at__gt=start)
            .filter(created_at__lt=end)
            .filter(provider__in=providers)
            .prefetch_related("pay_object__performance__production__society")
        )

        for payment in self.matched_payments:
            # Handle production
            if payment.pay_object and payment.pay_object.performance:
                self.production_totals.merge_push(
                    ObjectTotal(
                        payment.pay_object.performance.production, payment.value
                    )
                )

                # Handle society
                self.society_totals.merge_push(
                    ObjectTotal(
                        payment.pay_object.performance.production.society, payment.value
                    )
                )

            # Handle Provider
            self.provider_totals.merge_push(
                ObjectTotal(payment.provider, payment.value)
            )
