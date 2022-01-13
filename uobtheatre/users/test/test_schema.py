from unittest.mock import patch

import pytest
from graphql_auth.models import UserStatus
from graphql_relay.node.node import to_global_id

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.users.abilities import OpenAdmin, OpenBoxoffice
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_user_schema(gql_client):

    user = gql_client.login().user

    # Create some booking
    bookings = [BookingFactory(user=user) for i in range(4)]

    # Create an irrelevant user with some bookings
    # irrelevant_user = UserFactory()
    # _ = [BookingFactory(user=irrelevant_user) for i in range(4)]

    response = gql_client.execute(
        """
        {
	      me {
            firstName
            lastName
            email
            isStaff
            dateJoined
            id
            bookings {
              edges {
                node {
                  id
                }
              }
            }
          }
        }
        """
    )

    assert list(user.bookings.all()) == bookings
    assert response == {
        "data": {
            "me": {
                "firstName": user.first_name,
                "lastName": user.last_name,
                "email": user.email,
                "isStaff": user.is_staff,
                "dateJoined": user.date_joined.isoformat(),
                "id": to_global_id("UserNode", user.id),
                "bookings": {
                    "edges": [
                        {"node": {"id": to_global_id("BookingNode", booking.id)}}
                        for booking in bookings
                    ]
                },
            }
        }
    }


@pytest.mark.django_db
def test_user_schema_unauthenticated(gql_client):
    gql_client.logout()
    response = gql_client.execute(
        """
        {
	  me {
            email
          }
        }
        """
    )

    assert response == {"data": {"me": None}}


@pytest.mark.django_db
def test_user_field_error(gql_client):
    UserFactory()
    response = gql_client.execute(
        """
        mutation {
          register(
            email: "test@email.com"
            password1: "strongpassword"
            password2: "notsostrongpassword"
            firstName: "Tom"
            lastName: "Streuli"
          ) {
            success,
            errors {
              __typename
              ... on NonFieldError {
                message
                code
              }
              ... on FieldError {
                message
                field
                code
              }
            }
          }
        }
        """
    )

    assert response == {
        "data": {
            "register": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "The two password fields didn’t match.",
                        "field": "password2",
                        "code": "password_mismatch",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_user_wrong_credentials(gql_client):
    response = gql_client.execute(
        """
        mutation {
          login(email:"fakeaccount@email.com", password:"strongpassword"){
            token
            success
            errors {
              ... on FieldError {
                message
                field
                code
              }
              ... on NonFieldError {
                message
                code
              }
            }
          }
        }
        """
    )
    assert response == {
        "data": {
            "login": {
                "token": None,
                "success": False,
                "errors": [
                    {
                        "message": "Please, enter valid credentials.",
                        "code": "invalid_credentials",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_user_register(gql_client):
    # Create an account
    response = gql_client.execute(
        """
        mutation {
          register(
            email: "test@email.com"
            password1: "strongpassword"
            password2: "strongpassword"
            firstName: "James"
            lastName: "Tooof"
          ) {
            success
          }
        }
        """
    )

    login_query = """
        mutation {
          login(email:"test@email.com", password:"strongpassword"){
            token
            refreshToken
            success
            errors {
              __typename
              ... on NonFieldError {
                code
                message
              }
            }
            user {
              firstName
            }
          }
        }
        """

    # Now check we cannot login in (unverified)
    response = gql_client.execute(login_query)
    assert response["data"]["login"]["errors"] == [
        {
            "__typename": "NonFieldError",
            "code": "not_verified",
            "message": "Please verify your account.",
        }
    ]

    # Verify the user
    user_status = UserStatus.objects.get(user__email="test@email.com")
    user_status.verified = True
    user_status.save()

    # Assert the verify user can login
    response = gql_client.execute(login_query)
    response_data = response["data"]["login"]
    # Assert no errors
    assert all(
        [
            not response.get("errors", None),
            not response_data["errors"],
            response_data["success"] is True,
        ]
    )

    # Check the token is valid
    assert isinstance(response_data["token"], str) and len(response_data["token"]) > 150
    assert (
        isinstance(response_data["refreshToken"], str)
        and len(response_data["refreshToken"]) > 30
    )

    # Check user is correct
    assert response_data["user"]["firstName"] == "James"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_can_open_boxoffice, user_can_open_admin",
    [
        (True, False),
        (False, True),
        (True, True),
        (False, False),
    ],
)
def test_user_schema_abilities(
    user_can_open_boxoffice, user_can_open_admin, gql_client
):
    gql_client.login()
    with patch.object(
        OpenBoxoffice, "user_has", return_value=user_can_open_boxoffice
    ) as mock_open_boxoffice, patch.object(
        OpenAdmin, "user_has", return_value=user_can_open_admin
    ) as mock_open_admin:
        response = gql_client.execute(
            """
            {
	          me {
                permissions
              }
            }
            """
        )

    mock_open_boxoffice.assert_called_once_with(gql_client.user)
    mock_open_admin.assert_called_once_with(gql_client.user)
    permissions = response["data"]["me"]["permissions"]
    assert ("boxoffice_open" in permissions) == user_can_open_boxoffice
    assert ("admin_open" in permissions) == user_can_open_admin
