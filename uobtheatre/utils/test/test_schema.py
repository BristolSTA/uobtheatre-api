import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.utils.schema import IdInputField


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
    gql_client.login().execute(
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
