import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.productions.test.factories import PerformanceFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "report_name, expected_uri",
    [
        (
            "PeriodTotals",
            "/reports/period_totals/2020-01-01%2000:00:00/2021-01-01%2000:00:00",
        ),
        (
            "OutstandingPayments",
            "/reports/outstanding_society_payments",
        ),
    ],
)
def test_can_generate_report_link_for_finance_reports(
    gql_client, report_name, expected_uri
):
    request = """
        mutation{
            generateReport(name: "%s", startTime: "2020-01-01T00:00:00", endTime:"2021-01-01T00:00:00") {
                downloadUri

            }
        }
    """
    gql_client.login()
    assign_perm("reports.finance_reports", gql_client.user)
    response = gql_client.execute(request % report_name)
    split_url = response["data"]["generateReport"]["downloadUri"].split("?")
    assert split_url[0] == expected_uri
    assert split_url[1] is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "report_name",
    [
        ("PeriodTotals",),
        ("OutstandingPayments",),
    ],
)
def test_unauthorized_cant_generate_finance_reports(gql_client, report_name):
    request = """
        mutation{
            generateReport(name: "%s", startTime: "2020-01-01T00:00:00", endTime:"2021-01-01T00:00:00") {
                downloadUri
                errors {
                ... on NonFieldError {
                    message
                }
                }
            }
        }
    """
    gql_client.login()
    response = gql_client.execute(request % report_name)
    assert response["data"]["generateReport"]["downloadUri"] is None
    assert (
        response["data"]["generateReport"]["errors"][0]["message"]
        == "You are not authorized to perform this action"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "without_perm,invalid_id",
    [(False, False), (True, False), (False, True)],
)
def test_can_generate_report_for_performance_bookings(
    gql_client, without_perm, invalid_id
):
    performance = PerformanceFactory()
    request = """
        mutation{
            generateReport(name: "PerformanceBookings", options: [{name:"id",value:"%s"}]) {
                downloadUri
                errors {
                ... on NonFieldError {
                    message
                }
                ... on FieldError {
                    message
                    field
                }
                }
            }
        }
    """ % to_global_id(
        "PerformanceNode", performance.id if not invalid_id else performance.id + 1
    )

    gql_client.login()
    if not without_perm:
        assign_perm("change_production", gql_client.user, performance.production)

    response = gql_client.execute(request)

    if without_perm:
        assert (
            response["data"]["generateReport"]["errors"][0]["message"]
            == "You are not authorized to perform this action"
        )
    elif invalid_id:
        assert response["data"]["generateReport"]["errors"][0] == {
            "message": "Invalid performance ID option",
            "field": "options",
        }
    else:
        split_url = response["data"]["generateReport"]["downloadUri"].split("?")
        assert split_url[0] == "/reports/performance_bookings"
        assert split_url[1] is not None


@pytest.mark.django_db
def test_requesting_nonexistant_report(gql_client):
    request = """
        mutation{
            generateReport(name: "FakeReport") {
                downloadUri
                success
                errors {
                    __typename
                    ... on FieldError {
                        message
                        field
                    }
                }
            }
        }
    """

    response = gql_client.login().execute(request)

    assert response["data"]["generateReport"]["downloadUri"] is None
    assert response["data"]["generateReport"]["success"] is False
    assert response["data"]["generateReport"]["errors"][0]["__typename"] == "FieldError"
    assert response["data"]["generateReport"]["errors"][0]["field"] == "name"
    assert (
        response["data"]["generateReport"]["errors"][0]["message"]
        == "No report found matching 'FakeReport'"
    )


@pytest.mark.django_db
def test_cant_generate_when_not_logged_in(gql_client):
    request = """
        mutation{
            generateReport(name: "PeriodTotals") {
                downloadUri
                success
                errors {
                    __typename
                    ... on NonFieldError {
                        message
                    }
                }
            }
        }
    """

    response = gql_client.execute(request)

    assert response["data"]["generateReport"]["downloadUri"] is None
    assert response["data"]["generateReport"]["success"] is False
    assert (
        response["data"]["generateReport"]["errors"][0]["message"]
        == "Authentication Error"
    )
