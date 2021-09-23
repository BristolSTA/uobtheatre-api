from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Union

from django.db import connection
from graphql_relay.node.node import from_global_id

from uobtheatre.bookings.models import Booking
from uobtheatre.payments.models import Payment
from uobtheatre.productions.models import Performance, Production
from uobtheatre.users.models import User
from uobtheatre.utils.exceptions import AuthorizationException, GQLException


def get_option(options: List, name: str, default=None):
    return next(
        (option["value"] for option in options if option["name"] == name), default
    )


def require_option(options: List, option_name):
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

    def __init__(self):
        self.datasets = []
        self.meta = []

    def dataset_by_name(self, name: str) -> Union[DataSet, None]:
        return next(
            (dataset for dataset in self.datasets if dataset.name == name), None
        )

    def get_meta_array(self):
        return [[meta.name, meta.value] for meta in self.meta]

    @staticmethod
    def authorize_user(user: User, options: List):
        raise NotImplementedError()

    @staticmethod
    def validate_options(options: List):
        pass


class PeriodTotalsBreakdown(Report):
    """Generates a report on payments made via specified providers over a given time period"""

    def __init__(self, start: datetime, end: datetime) -> None:
        super().__init__()
        production_totals_set = DataSet(
            "Production Totals", ["Production ID", "Production Name", "Total Income"]
        )

        provider_totals_set = DataSet(
            "Provider Totals", ["Provider Name", "Total Income"]
        )

        payments = (
            Payment.objects.filter(created_at__gt=start)
            .filter(created_at__lt=end)
            .prefetch_related("pay_object__performance__production__society")
        )

        self.meta.append(MetaItem("No. of Payments", str(len(payments))))
        self.meta.append(
            MetaItem("Total Income", str(sum([payment.value for payment in payments])))
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
                payment.provider,
                [
                    payment.provider,
                    0,
                ],
            )
            row[1] += payment.value

        self.datasets.extend(
            [
                provider_totals_set,
                production_totals_set,
                DataSet(
                    "Payments",
                    ["Payment ID", "Timestamp", "Pay Object ID", "Payment Value"],
                    [
                        [
                            str(payment.id),
                            payment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                            str(payment.pay_object.id) if payment.pay_object else "",
                            str(payment.value),
                        ]
                        for payment in payments
                    ],
                ),
            ]
        )

    @staticmethod
    def authorize_user(user: User, options: List):
        if not user.has_perm("reports.finance_reports"):
            raise AuthorizationException()


class OutstandingSocietyPayments(Report):
    """Generates a report on outstanding balances to be paid to societies"""

    def __init__(self) -> None:
        super().__init__()
        productions_dataset = DataSet(
            "Productions",
            [
                "Production ID",
                "Production Name",
                "Society ID",
                "Society Name",
                "Society Net Income",
                "STA Fees",
            ],
        )

        societies_dataset = DataSet(
            "Societies",
            [
                "Society ID",
                "Society Name",
                "Total Ammount Due",
            ],
        )

        # Get productions that are marked closed
        productions = Production.objects.filter(
            status=Production.Status.CLOSED
        ).prefetch_related("society")

        sta_total_due = 0

        for production in productions:
            production_society_net_income = production.sales_breakdown[
                "society_income_total"
            ]
            production_sta_fees = production.sales_breakdown["misc_costs_total"]
            sta_total_due += production_sta_fees

            productions_dataset.find_or_create_row_by_first_column(
                production.id,
                [
                    production.id,
                    production.name,
                    production.society.id,
                    production.society.name,
                    production_society_net_income,
                    production_sta_fees,
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
            row[2] += production_society_net_income

        societies_dataset.add_row(["", "Stage Technicians' Association", sta_total_due])
        self.meta.append(
            MetaItem(
                "Total Outstanding",
                str(sum([row[2] for row in societies_dataset.data])),
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

    def __init__(self, performance: Performance) -> None:
        super().__init__()
        bookings_dataset = DataSet(
            "Bookings",
            ["ID", "Reference", "Name", "Email", "Tickets", "Total Paid (Pence)"],
        )

        self.meta.append(MetaItem("Performance", str(performance)))
        print(len(connection.queries))
        for booking in (
            performance.bookings.filter(status=Booking.BookingStatus.PAID)
            .prefetch_related(
                "payments", "user", "tickets__seat_group", "tickets__concession_type"
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
                    str(booking.total_paid),
                ]
            )
        print(len(connection.queries))
        print(connection.queries)

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

    @staticmethod
    def validate_options(options: List):
        # Need a valid performance id
        require_option(options, "id")
        if not Performance.objects.filter(
            pk=from_global_id(get_option(options, "id"))[1]
        ).exists():
            raise GQLException(message="Invalid performance ID option", field="options")
