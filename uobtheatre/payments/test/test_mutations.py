import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import FinancialTransfer, Transaction
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import SquarePOS

from ...societies.test.factories import SocietyFactory


@pytest.mark.django_db
def test_cancel_payment_completed_payment(gql_client):
    gql_client.login()
    booking = BookingFactory(creator=gql_client.user)
    payment = TransactionFactory(
        pay_object=booking,
        status=Transaction.Status.COMPLETED,
        provider_name=SquarePOS.name,
    )

    response = gql_client.execute(
        """
        mutation {
          cancelPayment(paymentId: "%s") {
            success
            errors {
                __typename
                ... on NonFieldError {
                    message
                    code
                }
            }
          }
        }
        """
        % to_global_id("TransactionNode", payment.id)
    )

    assert response["data"]["cancelPayment"]["errors"] == [
        {
            "__typename": "NonFieldError",
            "message": "A payment must be in progress to be canceled.",
            "code": "400",
        }
    ]


@pytest.mark.django_db
def test_cancel_payment_success(gql_client, mock_square):
    gql_client.login()
    booking = BookingFactory(creator=gql_client.user)
    payment = TransactionFactory(
        pay_object=booking,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
    )

    with mock_square(
        SquarePOS.client.terminal,
        "cancel_terminal_checkout",
        body={},
        status_code=200,
        success=True,
    ):
        response = gql_client.execute(
            """
            mutation {
              cancelPayment(paymentId: "%s") {
                success
                errors {
                    __typename
                    ... on NonFieldError {
                        message
                        code
                    }
                }
              }
            }
            """
            % to_global_id("TransactionNode", payment.id)
        )
    assert response["data"]["cancelPayment"]["success"]
    assert not response["data"]["cancelPayment"]["errors"]


@pytest.mark.django_db
def test_cancel_payment_not_creator_of_booking(gql_client):
    gql_client.login()
    booking = BookingFactory()
    payment = TransactionFactory(
        pay_object=booking,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
    )

    response = gql_client.execute(
        """
        mutation {
          cancelPayment(paymentId: "%s") {
            success
            errors {
                __typename
                ... on NonFieldError {
                    message
                    code
                }
            }
          }
        }
        """
        % to_global_id("TransactionNode", payment.id)
    )

    assert response["data"]["cancelPayment"]["errors"] == [
        {
            "__typename": "NonFieldError",
            "message": "You do not have permission to cancel this payment.",
            "code": "403",
        }
    ]


@pytest.mark.django_db
def test_record_transfer(gql_client):
    gql_client.login().user.assign_perm("payments.create_transfer")

    society = SocietyFactory()
    assert FinancialTransfer.objects.count() == 0

    response = gql_client.execute(
        """
        mutation {
            recordFinancialTransfer(societyId: "%s", value: 1050, method: INTERNAL) {
                success
            }
        }
        """
        % to_global_id("SocietyNode", society.id)
    )
    assert response["data"]["recordFinancialTransfer"]["success"] is True
    assert FinancialTransfer.objects.count() == 1


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
    gql_client.login().user.assign_perm("payments.create_transfer")

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
