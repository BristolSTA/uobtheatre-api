from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.http.response import HttpResponse
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from graphql_relay.node.node import to_global_id

from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.reports.utils import ExcelReport, generate_report_download_signature
from uobtheatre.reports.views import ValidSignatureMiddleware
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_validate_signature_middleware_invalid_reportname():
    middleware = ValidSignatureMiddleware(None, "MyReport")

    request = RequestFactory().get(
        "/?signature="
        + generate_report_download_signature(UserFactory(), "AnotherReport")
    )
    response = middleware.process_request(request)

    assert isinstance(response, HttpResponse)
    assert response.status_code == 403
    assert response.content == b"Invalid signature. Maybe this link has expired?"


# pylint: disable=missing-class-docstring
class PeriodTotalsTests(TestCase):
    @pytest.mark.django_db
    def test_can_access(self):
        with patch.object(
            ExcelReport, "datasets_to_response", return_value=HttpResponse()
        ):
            response = self.client.get(
                reverse(
                    "period_totals",
                    args=(datetime.now() - timedelta(weeks=100), datetime.now()),
                )
                + "?signature=%s"
                % generate_report_download_signature(UserFactory(), "PeriodTotals")
            )
        self.assertEqual(response.status_code, 200)

    def test_requires_signature(self):
        response = self.client.get(
            reverse(
                "period_totals",
                args=(datetime.now() - timedelta(weeks=100), datetime.now()),
            )
        )
        self.assertEqual(response.status_code, 403)


class SocietyOutstandingPaymentsTests(TestCase):
    @pytest.mark.django_db
    def test_can_access(self):
        with patch.object(
            ExcelReport, "datasets_to_response", return_value=HttpResponse()
        ):
            response = self.client.get(
                reverse(
                    "outstanding_society_payments",
                )
                + "?signature=%s"
                % generate_report_download_signature(
                    UserFactory(), "OutstandingPayments"
                )
            )
        self.assertEqual(response.status_code, 200)

    def test_requires_signature(self):
        response = self.client.get(
            reverse(
                "outstanding_society_payments",
            )
        )
        self.assertEqual(response.status_code, 403)


class PerformanceBookingsTests(TestCase):
    @pytest.mark.django_db
    def test_can_access(self):
        with patch.object(
            ExcelReport, "datasets_to_response", return_value=HttpResponse()
        ):
            response = self.client.get(
                reverse(
                    "performance_bookings",
                )
                + "?signature=%s"
                % generate_report_download_signature(
                    UserFactory(),
                    "PerformanceBookings",
                    [
                        {
                            "name": "id",
                            "value": to_global_id(
                                "PerformanceNode", PerformanceFactory().id
                            ),
                        }
                    ],
                )
            )
        self.assertEqual(response.status_code, 200)

    def test_requires_signature(self):
        response = self.client.get(
            reverse(
                "performance_bookings",
            )
        )
        self.assertEqual(response.status_code, 403)