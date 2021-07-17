import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import PaidBookingFactory
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.utils.schema import IdInputField


@pytest.mark.django_db
def test_id_input_field_wrong_thing(gql_client, gql_id):
    assert IdInputField.parse_literal(1.2) is None


@pytest.mark.django_db
def test_auth_required_mixin(gql_client_flexible, gql_id):
    booking = PaidBookingFactory()
    client = gql_client_flexible
    client.logout()

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
    response = client.execute(request_query % gql_id(booking.id, "BookingNode"))
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
def test_id_input_field_parse_value(gql_client_flexible):
    performance = PerformanceFactory()
    response = gql_client_flexible.execute(
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

    print(response)
    booking = Booking.objects.first()
    assert booking.performance == performance
