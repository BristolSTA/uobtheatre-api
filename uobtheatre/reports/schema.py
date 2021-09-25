from typing import List

import graphene
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from graphene.types.datetime import DateTime
from graphene.types.scalars import String

import uobtheatre.reports.reports as reports
from uobtheatre.reports.utils import generate_report_download_signature
from uobtheatre.utils.exceptions import GQLException, SafeMutation
from uobtheatre.utils.schema import AuthRequiredMixin

available_reports = {
    "PeriodTotals": {
        "cls": reports.PeriodTotalsBreakdown,
        "uri": "period_totals",
    },
    "OutstandingPayments": {
        "cls": reports.OutstandingSocietyPayments,
        "uri": "outstanding_society_payments",
    },
    "PerformanceBookings": {
        "cls": reports.PerformanceBookings,
        "uri": "performance_bookings",
    },
}


class ReportOption(graphene.InputObjectType):
    name = graphene.String(required=True)
    value = graphene.String(required=True)


class GenerateReport(AuthRequiredMixin, SafeMutation):
    """Mutation to generate a report"""

    class Arguments:
        name = graphene.String(required=True)
        start_time = graphene.DateTime()
        end_time = graphene.DateTime()
        options = graphene.List(ReportOption)

    download_uri = graphene.String()

    @classmethod
    def resolve_mutation(
        cls,
        _,
        info,
        name: String,
        start_time: DateTime = None,
        end_time: DateTime = None,
        options: List = None,
    ):
        if not name in available_reports:
            raise GQLException(
                message="No report found matching '%s'" % name, field="name"
            )

        matching_report = available_reports[name]

        # Validate and authorize
        matching_report["cls"].validate_options(options)
        matching_report["cls"].authorize_user(info.context.user, options)

        download_uri = None

        # Generate signature to authorize user to access
        signature = generate_report_download_signature(info.context.user, name, options)
        try:
            download_uri = reverse(
                str(matching_report["uri"]),
                kwargs={"start_time": start_time, "end_time": end_time},
            )
        except NoReverseMatch:
            download_uri = reverse(
                str(matching_report["uri"]),
            )

        return GenerateReport(download_uri=download_uri + "?signature=" + signature)


class Mutation(graphene.ObjectType):
    generate_report = GenerateReport.Field()