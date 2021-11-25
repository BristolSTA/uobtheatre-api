import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory, PerformanceSeatingFactory
from uobtheatre.productions.models import Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.exceptions import AuthorizationException
from uobtheatre.utils.schema import IdInputField, ModelDeletionMutation


@pytest.mark.django_db
def test_id_input_field_wrong_thing():
    assert IdInputField.parse_literal(1.2) is None


@pytest.mark.django_db
def test_auth_required_mixin(gql_client):
    booking = BookingFactory()
    client = gql_client

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 102
            nonce: "cnon:card-nonce-ok"
        ) {
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
    response = client.execute(request_query % to_global_id("BookingNode", booking.id))
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "Authentication Error",
                        "code": "401",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_id_input_field_parse_value(gql_client):
    performance = PerformanceFactory()
    PerformanceSeatingFactory(performance=performance)
    gql_client.login()
    gql_client.execute(
        """
        mutation($id: IdInputField!) {
          createBooking(
           performanceId: $id
          ) {
            booking {
              id
            }
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
        """,
        variable_values={"id": to_global_id("PerformanceNode", performance.id)},
    )

    booking = Booking.objects.first()
    assert booking.performance == performance


@pytest.mark.django_db
@pytest.mark.parametrize("with_delete_perm", [False, True])
def test_model_deletion_mutation_authorisation(with_delete_perm):
    user = UserFactory()
    production = ProductionFactory()

    class FakeModelDeletionMutation(ModelDeletionMutation):
        class Meta:
            model = Production

    mutation = FakeModelDeletionMutation()

    if with_delete_perm:
        assign_perm("delete_production", user, production)

    context = type(
        "obj", (object,), {"context": type("obj", (object,), {"user": user})}
    )

    if with_delete_perm:
        mutation.authorize_request(
            None,
            context,
            id=production.id,
        )
    else:
        with pytest.raises(AuthorizationException):
            mutation.authorize_request(
                None,
                context,
                id=production.id,
            )
