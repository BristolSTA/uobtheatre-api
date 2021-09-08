import pytest


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
def test_can_generate_report_link(gql_client, report_name, expected_uri):
    request = """
        mutation{
            generateReport(name: "%s", startTime: "2020-01-01T00:00:00", endTime:"2021-01-01T00:00:00") {
                downloadUri
            }
        }
    """

    response = gql_client.login().execute(request % report_name)

    assert response["data"]["generateReport"]["downloadUri"] == expected_uri


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


@pytest.mark.django_db
def test_cant_generate_link_without_perms():
    # TODO
    pass
