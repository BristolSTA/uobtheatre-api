from typing import List

import graphene
from django.conf import settings
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from graphene.types.datetime import DateTime
from graphene.types.scalars import String

from uobtheatre.reports import reports
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


class DataSetNode(graphene.ObjectType):
    name = graphene.String(required=True)
    headings = graphene.List(graphene.String, required=True)
    data = graphene.List(graphene.List(graphene.String), required=True)


class MetaItemNode(graphene.ObjectType):
    name = graphene.String(required=True)
    value = graphene.String(required=True)


class ReportNode(graphene.ObjectType):
    datasets = graphene.List(DataSetNode)
    meta = graphene.List(MetaItemNode)


class GenerateReport(AuthRequiredMixin, SafeMutation):
    """Mutation to generate a report"""

    class Arguments:
        name = graphene.String(required=True)
        start_time = graphene.DateTime()
        end_time = graphene.DateTime()
        options = graphene.List(ReportOption)

    download_uri = graphene.String()
    report = graphene.Field(ReportNode)

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
        options = options or []
        # If a date range is provided
        if end_time or start_time:
            # Validate both end and start are provided
            if end_time is None:
                raise GQLException(
                    message="An end time must be provided when using a start time",
                    field="end_time",
                )
            if start_time is None:
                raise GQLException(
                    message="A start time must be provided when using an end time",
                    field="start_time",
                )
            # And that end time is after start time
            if end_time <= start_time:
                raise GQLException(message="The end time must be after the start time")
            options.append({"name": "start_time", "value": str(start_time)})
            options.append({"name": "end_time", "value": str(end_time)})

        matching_report = available_reports[name]

        # Validate and authorize
        matching_report["cls"].validate_options(options)  # type: ignore
        matching_report["cls"].authorize_user(info.context.user, options)  # type: ignore

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

        return GenerateReport(
            download_uri=settings.BASE_URL + download_uri + "?signature=" + signature,
            report=matching_report["cls"](options),
        )


class Mutation(graphene.ObjectType):
    generate_report = GenerateReport.Field()
