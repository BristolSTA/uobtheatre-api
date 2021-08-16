import graphene
from django.urls import reverse
from graphene.types.datetime import DateTime
from graphene.types.scalars import String

import uobtheatre.reports.reports as reports
from uobtheatre.utils.exceptions import GQLNonFieldException, SafeMutation
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
}


class GenereateReport(AuthRequiredMixin, SafeMutation):
    """Mutation to generate a report"""

    class Arguments:
        name = graphene.String(required=True)
        start_time = graphene.DateTime()
        end_time = graphene.DateTime()

    donwload_uri = graphene.String()

    @classmethod
    def resolve_mutation(
        cls,
        _,
        info,
        name: String,
        start_time: DateTime = None,
        end_time: DateTime = None,
    ):
        if not name in available_reports:
            raise GQLNonFieldException("No report found matching '%s'" % name)

        matching_report = available_reports[name]

        return GenereateReport(
            donwload_uri=reverse(
                str(matching_report["uri"]),
                kwargs={"start_time": start_time, "end_time": end_time},
            )
        )


class Mutation(graphene.ObjectType):
    generate_report = GenereateReport.Field()
