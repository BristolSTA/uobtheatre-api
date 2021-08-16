from django.http import HttpResponse
from xlsxwriter.utility import xl_rowcol_to_cell

from uobtheatre.reports.utils import ExcelReport

from . import reports


def period_totals(request, start_time, end_time):
    """Generates excel for period totals report

    Args:
        request (HttpRequest): The HttpRequest
        start_time (DateTime): Start date for the report
        end_time (DateTime): End date for the report

    Returns:
        HttpResponse: The HttpResponse
    """

    # Generate report
    report = reports.PeriodTotalsBreakdown(
        start_time,
        end_time,
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
            ["Period From", str(start_time)],
            ["Period To", str(end_time)],
            ["No. of Payments", len(report.dataset_by_name("payments").items)],
        ],
        request.user,
    )

    totals_breakdown_start_row = excel.row_tracker - 1

    # Add Provider Totals
    excel.write_list(
        (totals_breakdown_start_row, 0),  # A
        [
            provider_item.subject
            for provider_item in report.dataset_by_name("provider_totals").items
        ],
        title="Totals By Provider",
    )
    excel.write_list(
        (totals_breakdown_start_row + 1, 1),  # B
        [
            provider_item.data / 100
            for provider_item in report.dataset_by_name("provider_totals").items
        ],
        items_format="currency",
    )

    # Add Production Totals
    excel.write_list(
        (totals_breakdown_start_row, 3),  # D
        [
            str(production_item.subject)
            for production_item in report.dataset_by_name("production_totals").items
        ],
        title="Totals By Production",
    )
    excel.write_list(
        (totals_breakdown_start_row + 1, 4),  # E
        [
            str(production_item.subject.society)
            for production_item in report.dataset_by_name("production_totals").items
        ],
    )
    excel.write_list(
        (totals_breakdown_start_row + 1, 5),  # F
        [
            production_item.data / 100
            for production_item in report.dataset_by_name("production_totals").items
        ],
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

    for i, society_item in enumerate(report.dataset_by_name("societies").items):
        start_col = i + 2 * i
        excel.write_list(
            (totals_row_start, start_col),
            [
                str(production_item.subject)
                for production_item in society_item.data.items
            ],
            title=str(society_item.subject),
        )

        excel.write_list(
            (totals_row_start + 1, start_col + 1),
            [production_item.data / 100 for production_item in society_item.data.items],
            items_format="currency",
        )

        if not i == 0:
            excel.set_col_width(start_col, start_col, 20)

    # Add SUM Totals
    excel.increment_row_tracker()

    for i, society_item in enumerate(report.dataset_by_name("societies").items):
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
