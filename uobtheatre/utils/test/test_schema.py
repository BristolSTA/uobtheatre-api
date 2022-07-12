from unittest.mock import patch

import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory, PerformanceSeatingFactory
from uobtheatre.discounts.test.factories import ConcessionTypeFactory
from uobtheatre.productions.models import Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.exceptions import AuthorizationException
from uobtheatre.utils.schema import (
    AssignedUsersMixin,
    IdInputField,
    ModelDeletionMutation,
    UserPermissionFilterMixin,
)


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
            id: "%s"
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
    psg = PerformanceSeatingFactory(performance=performance)
    concession = ConcessionTypeFactory()

    with patch(
        "uobtheatre.productions.abilities.BookForPerformance.user_has_for",
        return_value=True,
    ):
        gql_client.login().execute(
            """
        mutation($id: ID!, $sgId: IdInputField!, $ctId: IdInputField!) {
        booking(
            input: {performance: $id, tickets: [{seatGroupId: $sgId, concessionTypeId: $ctId}]}
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
            variable_values={
                "id": to_global_id("PerformanceNode", performance.id),
                "sgId": to_global_id("SeatGroup", psg.seat_group.id),
                "ctId": to_global_id("ConcessionType", concession.id),
            },
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
