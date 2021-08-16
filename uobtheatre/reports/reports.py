from abc import ABC
from datetime import datetime
from typing import List, Union

from uobtheatre.payments import payment_methods
from uobtheatre.payments.models import Payment
from uobtheatre.productions.models import Production


class DataItem:
    def __init__(self, data, subject=None):
        self.subject = subject
        self.data = data


class MetaItem:
    def __init__(self, name: str, value):
        self.name = name
        self.value = value


class DataSet:
    """A data set represents a list of data items."""

    def __init__(
        self, name: str, items: List[DataItem] = None, meta: List[MetaItem] = None
    ):
        self.name = name
        self.items = items if items else []
        self.meta = meta if meta else []

    def find_item_by_subject(self, subject) -> Union[DataItem, None]:
        """Find a data item in the set by a subject"""
        return next((item for item in self.items if item.subject == subject), None)

    def find_or_create_item_by_subject(self, subject, data) -> DataItem:
        """Finds a data item in the set by subject. If it doesn't exist, creates a new data item with the given initial value"""
        return self.find_item_by_subject(subject) or self.create_item(data, subject)

    def create_item(self, *args) -> DataItem:
        """Creates a data item in the data set"""
        item = DataItem(*args)
        self.items.append(item)
        return item


class AbstractReport(ABC):
    def __init__(self):
        self.datasets = []

    def dataset_by_name(self, name: str) -> Union[DataSet, None]:
        return next(
            (dataset for dataset in self.datasets if dataset.name == name), None
        )


class PeriodTotalsBreakdown(AbstractReport):
    """Generates a report on payments made via specified providers over a given time period"""

    def __init__(self, start: datetime, end: datetime) -> None:
        super().__init__()
        production_totals_set = DataSet("production_totals")
        provider_totals_set = DataSet("provider_totals")
        payments = (
            Payment.objects.filter(created_at__gt=start)
            .filter(created_at__lt=end)
            .prefetch_related("pay_object__performance__production__society")
        )

        # Add all providers
        for provider in payment_methods.PaymentMethod.__all__:
            provider_totals_set.create_item(0, provider.name)

        for payment in payments:
            if payment.pay_object and payment.pay_object.performance:

                # Handle production
                production_set = production_totals_set.find_or_create_item_by_subject(
                    payment.pay_object.performance.production, 0
                )
                production_set.data += payment.value

            # Handle Provider
            provider_set = provider_totals_set.find_item_by_subject(payment.provider)
            if provider_set:
                provider_set.data += payment.value

        self.datasets.extend(
            [
                production_totals_set,
                provider_totals_set,
                DataSet("payments", [DataItem(payment) for payment in payments]),
            ]
        )


class OutstandingSocietyPayments(AbstractReport):
    """Generates a report on outstanding balances to be paid to societies"""

    def __init__(self) -> None:
        super().__init__()
        dataset = DataSet("societies")

        # Get productions that are marked closed
        productions = Production.objects.filter(
            status=Production.Status.CLOSED
        ).prefetch_related("society")

        for production in productions:
            production_society_income = production.sales_breakdown()["society_income"]
            society_data_item = dataset.find_item_by_subject(production.society)
            if not society_data_item:
                society_data_item = dataset.create_item(
                    DataSet("productions"), production.society
                )
            society_data_item.data.create_item(production_society_income, production)

        dataset.meta.append(
            MetaItem(
                "total",
                sum(
                    [
                        production_item.data
                        for society_item in dataset.items
                        for production_item in society_item.data.items
                    ]
                ),
            )
        )
        self.datasets.append(dataset)
