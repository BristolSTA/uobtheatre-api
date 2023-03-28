import abc
from abc import ABC
from dataclasses import dataclass, field
from typing import Dict, List, Union

from graphql_relay.node.node import from_global_id

from uobtheatre.bookings.models import Booking
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.productions.models import Performance, Production
from uobtheatre.users.models import User
from uobtheatre.utils.exceptions import AuthorizationException, GQLException


def get_option(options: List[Dict[str, str]], name: str, default=None):
    return next(
        (option["value"] for option in options if option["name"] == name), default
    )


def require_option(options: List[Dict[str, str]], option_name):
    if not get_option(options, option_name):
        raise GQLException(
            message="You must supply the %s option" % option_name, field="options"
        )


@dataclass
class MetaItem:
    name: str
    value: str


@dataclass
class DataSet:
    """A data set represents a table, with headers and rows of data"""

    name: str
    headings: List[str]
    data: List[List[str]] = field(default_factory=list)

    def add_row(self, data):
        self.data.append(data)

    def find_or_create_row_by_first_column(self, value, default_row_data):
        row = next((row for row in self.data if row[0] == value), None)
        if not row:
            row = default_row_data
            self.add_row(row)
        return row


class Report(ABC):
    """An abstract class for a generic report"""

    def __init__(self, options: list = None):
        self.datasets: list[DataSet] = []
        self.meta: list[MetaItem] = []
        self.options = options or []

        self.validate_options(self.options)

    @abc.abstractmethod
    def run(self):
        """Runs the report"""
        raise NotImplementedError()

    def dataset_by_name(self, name: str) -> Union[DataSet, None]:
        return next(
            (dataset for dataset in self.datasets if dataset.name == name), None
        )

    def get_meta_array(self):
        return [[meta.name, meta.value] for meta in self.meta]

    @staticmethod
    def authorize_user(user: User, options: List):
        raise NotImplementedError()

    @classmethod
    def validate_options(cls, options: List):
        pass

    def get_option(self, name, default=None):
        return get_option(self.options, name, default)


class TimeScopedReport(Report):
    @classmethod
    def validate_options(cls, options: List):
        super().validate_options(options)
        require_option(options, "start_time")
        require_option(options, "end_time")


class PeriodTotalsBreakdown(TimeScopedReport):
    """Generates a report on payments made via specified providers over a given time period"""

    def run(self):
        start = self.get_option("start_time")
        end = self.get_option("end_time")
        production_totals_set = DataSet(
            "Production Totals",
            ["Production ID", "Production Name", "Total Income (Pence)"],
        )

        provider_totals_set = DataSet(
            "Provider Totals", ["Provider Name", "Total Income (Pence)"]
        )

        payments = Transaction.objects.filter(
            created_at__gt=start,
            status=Transaction.Status.COMPLETED,
            created_at__lt=end,
        ).prefetch_related("pay_object__performance__production__society")

        # Resync any payments that dont have provider fees
        payments.missing_provider_fee().sync()  # type: ignore

        self.meta.append(MetaItem("No. of Payments", str(len(payments))))
        self.meta.append(
            MetaItem("Total Income", str(sum(payment.value for payment in payments)))
        )

        for payment in payments:
            # Handle production
            row = production_totals_set.find_or_create_row_by_first_column(
                payment.pay_object.performance.production.id
                if payment.pay_object
                else "",
                [
                    payment.pay_object.performance.production.id
                    if payment.pay_object
                    else "",
                    payment.pay_object.performance.production.name
                    if payment.pay_object
                    else "",
                    0,
                ],
            )
            row[2] += payment.value

            # Handle Provider
            row = provider_totals_set.find_or_create_row_by_first_column(
                payment.provider_name,
                [
                    payment.provider_name,
                    0,
                ],
            )
            row[1] += payment.value

        # Sort alphabetically
        provider_totals_set.data.sort(key=lambda provider: provider[0])
        production_totals_set.data.sort(key=lambda production: production[0])
        payments_data = [
            [
                str(payment.id),
                payment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                payment.type,
                str(payment.pay_object.id) if payment.pay_object else "",
                type(payment.pay_object).__name__ if payment.pay_object else "",
                str(
                    payment.pay_object.performance.production.id
                    if isinstance(payment.pay_object, Booking)
                    else ""
                ),
                str(
                    payment.pay_object.performance.production.name
                    if isinstance(payment.pay_object, Booking)
                    else ""
                ),
                str(payment.value),
                str(payment.provider_name),
                str(payment.provider_transaction_id or ""),
            ]
            for payment in payments
        ]
        payments_data.sort(key=lambda payment: payment[1])

        self.datasets.extend(
            [
                provider_totals_set,
                production_totals_set,
                DataSet(
                    "Payments",
                    [
                        "Payment ID",
                        "Timestamp",
                        "Payment Type",
                        "Pay Object ID",
                        "Pay Object Type",
                        "Production ID",
                        "Production",
                        "Payment Value",
                        "Provider",
                        "Provider ID",
                    ],
                    payments_data,
                ),
            ]
        )

    @staticmethod
    def authorize_user(user: User, options: List):
        if not user.has_perm("reports.finance_reports"):
            raise AuthorizationException()


class OutstandingSocietyPayments(Report):
    """Generates a report on outstanding balances to be paid to societies"""

    def run(self):
        productions_dataset = DataSet(
            "Productions",
            [
                "Production ID",
                "Production Name",
                "Society ID",
                "Society Name",
                "Total Payments",
                "Total Payments via Card",
                "Total Refunds",
                "Total Refunds via Card",
                "Net Transactions",
                "Net Transactions via Card",
                "Processing Fees",
                "STA Fees",
                "Society Net Income",
            ],
        )

        societies_dataset = DataSet(
            "Societies",
            [
                "Society ID",
                "Society Name",
                "Total Amount Due",
            ],
        )

        # Get productions that are marked closed
        productions = Production.objects.filter(
            status=Production.Status.CLOSED
        ).prefetch_related("society")

        # Sync all payments associated with these productions
        productions.transactions().missing_provider_fee().sync()  # type: ignore

        sta_total_due = 0

        for production in productions:
            sales_breakdown = production.sales_breakdown()
            production_sta_fees = sales_breakdown["app_payment_value"]
            sta_total_due += production_sta_fees

            if production.society is None:
                raise GQLException(f"Production {production.id} has no society")
            productions_dataset.find_or_create_row_by_first_column(
                production.id,
                [
                    production.id,
                    production.name,
                    production.society.id,
                    production.society.name,
                    sales_breakdown["total_payments"],
                    sales_breakdown["total_card_payments"],
                    sales_breakdown["total_refunds"],
                    sales_breakdown["total_card_refunds"],
                    sales_breakdown["net_transactions"],
                    sales_breakdown["net_card_transactions"],
                    sales_breakdown["provider_payment_value"],
                    production_sta_fees,
                    sales_breakdown["society_transfer_value"],
                ],
            )

            row = societies_dataset.find_or_create_row_by_first_column(
                production.society.id,
                [
                    production.society.id,
                    production.society.name,
                    0,
                ],
            )
            row[2] += sales_breakdown["society_transfer_value"]

        societies_dataset.add_row(["", "Stage Technicians' Association", sta_total_due])
        self.meta.append(
            MetaItem(
                "Total Outstanding",
                str(sum(row[2] for row in societies_dataset.data)),
            )
        )

        self.datasets.append(societies_dataset)
        self.datasets.append(productions_dataset)

    @staticmethod
    def authorize_user(user: User, options: List):
        if not user.has_perm("reports.finance_reports"):
            raise AuthorizationException()


class PerformanceBookings(Report):
    """Generates a report with the bookings for a production"""

    def run(self):
        performance = Performance.objects.get(
            pk=from_global_id(self.get_option("id"))[1]
        )
        bookings_dataset = DataSet(
            "Bookings",
            ["ID", "Reference", "Name", "Email", "Tickets", "Total Paid (Pence)"],
        )

        self.meta.append(MetaItem("Performance", str(performance)))
        for booking in (
            performance.bookings.filter(status=Payable.Status.PAID)
            .prefetch_related(
                "transactions",
                "user",
                "tickets__seat_group",
                "tickets__concession_type",
            )
            .all()
        ):
            bookings_dataset.add_row(
                [
                    booking.id,
                    booking.reference,
                    str(booking.user),
                    booking.user.email,
                    "\r\n".join([str(ticket) for ticket in booking.tickets.all()]),
                    str(booking.sales_breakdown.total_payments),
                ]
            )

        self.datasets.append(bookings_dataset)

    @staticmethod
    def authorize_user(user: User, options: List):
        if not user.has_perm(
            "change_production",
            Performance.objects.prefetch_related("production")
            .get(pk=from_global_id(get_option(options, "id"))[1])
            .production,
        ):
            raise AuthorizationException()

    @classmethod
    def validate_options(cls, options: List):
        # Need a valid performance id
        require_option(options, "id")
        if not Performance.objects.filter(
            pk=from_global_id(get_option(options, "id"))[1]
        ).exists():
            raise GQLException(message="Invalid performance ID option", field="options")
