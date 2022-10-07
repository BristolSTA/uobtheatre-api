import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.finance.models import FinancialTransfer
from uobtheatre.societies.test.factories import SocietyFactory


@pytest.mark.django_db
@pytest.mark.parametrize("reason", [None, "My reason"])
def test_record_transfer(gql_client, reason):
    gql_client.login().user.assign_perm("finance.create_transfer")

    society = SocietyFactory()
    assert FinancialTransfer.objects.count() == 0

    response = gql_client.execute(
        """
        mutation {
            recordFinancialTransfer(societyId: "%s", value: 1050, method: INTERNAL %s) {
                success
            }
        }
        """
        % (
            to_global_id("SocietyNode", society.id),
            "" if not reason else f'reason: "{reason}"',
        )
    )

    assert response["data"]["recordFinancialTransfer"]["success"] is True
    assert FinancialTransfer.objects.count() == 1
    assert FinancialTransfer.objects.first().reason == reason


@pytest.mark.django_db
def test_record_transfer_fails_without_permission(gql_client):
    gql_client.login()

    society = SocietyFactory()

    response = gql_client.execute(
        """
        mutation {
            recordFinancialTransfer(societyId: "%s", value: 1050, method: INTERNAL) {
                success
                errors {
                    ... on FieldError {
                        message
                    }
                     ... on NonFieldError {
                        message
                    }
                }
            }
        }
        """
        % to_global_id("SocietyNode", society.id)
    )
    assert response["data"]["recordFinancialTransfer"]["success"] is False
    assert (
        response["data"]["recordFinancialTransfer"]["errors"][0]["message"]
        == "You are not authorized to perform this action"
    )
    assert FinancialTransfer.objects.count() == 0


@pytest.mark.django_db
def test_record_transfer_fails_with_invalid_society(gql_client):
    gql_client.login().user.assign_perm("finance.create_transfer")

    response = gql_client.execute(
        """
        mutation {
            recordFinancialTransfer(societyId: "%s", value: 1050, method: INTERNAL) {
                success
                errors {
                    ... on FieldError {
                        message
                    }
                     ... on NonFieldError {
                        message
                    }
                }
            }
        }
        """
        % to_global_id("SocietyNode", "1")
    )
    assert response["data"]["recordFinancialTransfer"]["success"] is False
    assert (
        response["data"]["recordFinancialTransfer"]["errors"][0]["message"]
        == "Object not found"
    )
    assert FinancialTransfer.objects.count() == 0
