from datetime import datetime

from django.http import HttpResponse
from xlsxwriter.utility import xl_rowcol_to_cell

from uobtheatre.payments.models import Payment
from uobtheatre.reports.utils import ExcelReport

from . import reports


def period_totals(request):
    """Generates excel for period totals report

    Args:
        request (HttpRequest): The HttpRequest

    Returns:
        HttpResponse: The HttpResponse
    """
    start = datetime(2020, 1, 1)  # Sometext TODO: Implement arguments for these
    end = datetime(2021, 12, 30)

    # Generate report
    report = reports.PeriodTotalsBreakdown(
        start,
        end,
        Payment.PaymentProvider.names,
    )

    excel = ExcelReport(
        "Period Totals Report",
        [
            "This report provides summaries and totals of payments taken and recorded.",
            "Totals are calcualted by summing the payments (which are positive in the chase of a charge, or negative for a refund).",
            "Totals are inclusive of any costs and fees that are charged to the society. Hence, these figures should not be used to calculate account transfers to societies.",
            "All currency is GBP.",
        ],
        [
            ["Period From", str(start)],
            ["Period To", str(end)],
            ["No. of Payments", len(report.matched_payments)],
        ],
        request.user,
    )

    totals_breakdown_start_row = excel.row_tracker - 1

    # Add Provider Totals
    excel.write_list(
        (totals_breakdown_start_row, 0),  # A
        [provider.object for provider in report.provider_totals.collection],
        title="Totals By Provider",
    )
    excel.write_list(
        (totals_breakdown_start_row + 1, 1),  # B
        [provider.total / 100 for provider in report.provider_totals.collection],
        items_format="currency",
    )

    # Add Production Totals
    excel.write_list(
        (totals_breakdown_start_row, 3),  # D
        [str(production.object) for production in report.production_totals.collection],
        title="Totals By Production",
    )
    excel.write_list(
        (totals_breakdown_start_row + 1, 4),  # E
        [
            str(production.object.society)
            for production in report.production_totals.collection
        ],
    )
    excel.write_list(
        (totals_breakdown_start_row + 1, 5),  # F
        [production.total / 100 for production in report.production_totals.collection],
        items_format="currency",
    )

    excel.increment_row_tracker()  # Add gap

    # Add SUM rows
    excel.write("A%s" % excel.row_tracker, "Total")
    excel.write_formula(
        "B%s" % excel.row_tracker,
        "=SUM(B%s:B%s)" % (totals_breakdown_start_row + 1, excel.row_tracker - 2),
        excel.formats["currency"],
    )
    excel.write("E%s" % excel.row_tracker, "Total")
    excel.write_formula(
        "F%s" % excel.row_tracker,
        "=SUM(F%s:F%s)" % (totals_breakdown_start_row + 1, excel.row_tracker - 2),
        excel.formats["currency"],
    )
    excel.increment_row_tracker()

    response = HttpResponse(
        excel.get_output(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        "attachment; filename=%s" % "card_totals_report.xlsx"
    )
    return response


def outstanding_society_payments(request):
    """Generates excel of society payments report"""
    report = reports.OutstandingSocietyPayments()

    excel = ExcelReport(
        "Outstanding Society Payments",
        [
            "This report details the production income due to societies at the time the report is generated.",
            "Once the payment has been made, this MUST be recorded on the system in order to remove the balance.",
            "All currency is GBP.",
        ],
        [],
        request.user,
    )

    totals_row_start = excel.row_tracker - 1

    for i, society_object_collection in enumerate(report.societies.values()):
        start_col = i + 2 * i
        excel.write_list(
            (totals_row_start, start_col),
            [
                str(production_object_total.object)
                for production_object_total in society_object_collection.collection
            ],
            title=str(society_object_collection.object),
        )

        excel.write_list(
            (totals_row_start + 1, start_col + 1),
            [
                production_object_total.total / 100
                for production_object_total in society_object_collection.collection
            ],
            items_format="currency",
        )

        if not i == 0:
            excel.set_col_width(start_col, start_col, 20)

    # Add SUM Totals
    excel.increment_row_tracker()

    for i, society_object_collection in enumerate(report.societies.values()):
        start_col = i + 2 * i

        excel.write(excel.row_tracker - 1, start_col, "Payment Due")
        excel.write_formula(
            excel.row_tracker - 1,
            start_col + 1,
            "=SUM(%s:%s)"
            % (
                xl_rowcol_to_cell(totals_row_start + 1, start_col + 1),
                xl_rowcol_to_cell(excel.row_tracker - 3, start_col + 1),
            ),
            excel.formats["currency"],
        )

    response = HttpResponse(
        excel.get_output(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        "attachment; filename=%s" % "outstanding_production_payments.xlsx"
    )
    return response
