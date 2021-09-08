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
        ]
        + report.get_meta_array(),
        request.user,
    )

    return excel.datasets_to_response(report.datasets)


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
        report.get_meta_array(),
        request.user,
    )

    return excel.datasets_to_response(report.datasets)
