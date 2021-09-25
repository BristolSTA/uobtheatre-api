from django.http.response import HttpResponse
from django.utils.decorators import decorator_from_middleware_with_args
from graphql_relay.node.node import from_global_id

from uobtheatre.productions.models import Performance
from uobtheatre.reports.exceptions import InvalidReportSignature
from uobtheatre.reports.utils import ExcelReport, validate_report_download_signature
from uobtheatre.users.models import User

from . import reports


class ValidSignatureMiddleware:
    """Middleware that validates and then injects the report download signature"""

    def __init__(self, get_response, report_name=None):
        self.get_response = get_response
        self.report_name = report_name

    def process_request(self, request):
        """Before request proccessed hook"""
        try:
            obj = validate_report_download_signature(request.GET.get("signature"))
            if obj["report"] != self.report_name:
                raise InvalidReportSignature()
            return None
        except InvalidReportSignature:
            return HttpResponse(
                content="Invalid signature. Maybe this link has expired?",
                status=403,
            )

    def process_view(self, request, _, __, ___):
        """Before view render hook"""
        request.signature_object = validate_report_download_signature(
            request.GET.get("signature")
        )
        request.report_options = request.signature_object["options"]
        request.user = User.objects.get(pk=request.signature_object["user_id"])


valid_signature = decorator_from_middleware_with_args(ValidSignatureMiddleware)


@valid_signature("PeriodTotals")
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


@valid_signature("OutstandingPayments")
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


@valid_signature("PerformanceBookings")
def performance_bookings(request):
    """Generates excel for period totals report

    Args:
        request (HttpRequest): The HttpRequest

    Returns:
        HttpResponse: The HttpResponse
    """

    # Generate report
    performance = Performance.objects.get(
        pk=from_global_id(reports.get_option(request.report_options, "id"))[1]
    )
    report = reports.PerformanceBookings(performance=performance)

    excel = ExcelReport(
        "Performance Bookings",
        [
            "This report provides details of the bookings for the specified performance",
        ],
        report.get_meta_array(),
        request.user,
    )

    return excel.datasets_to_response(report.datasets)
