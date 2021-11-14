import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory, PerformanceSeatingFactory
from uobtheatre.productions.models import Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.schema import IdInputField, UserPermissionFilterMixin


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
@pytest.mark.parametrize(
    "permission,expected_ids",
    [
        (None, [1, 2]),
        ("add_production", []),
        ("view_production", [1]),
        ("productions.view_production", [1]),
        ("invalid_permission", []),
    ],
)
def test_user_has_permission_mixin(permission, expected_ids):
    user = UserFactory()
    prod_1 = ProductionFactory(id=1)
    ProductionFactory(id=2)
    assign_perm("view_production", user, prod_1)

    filter_set = UserPermissionFilterMixin(
        data={"user_has_permission": permission},
        request=type("", (object,), {"user": user})(),
        queryset=Production.objects.all(),
    )

    productions_ids = [production.id for production in filter_set.qs.all()]
    assert productions_ids == expected_ids
