import uuid
from unittest.mock import patch

import pytest
from django.test import override_settings
from graphql_relay.node.node import to_global_id

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.graphql_auth.models import UserStatus
from uobtheatre.users.abilities import OpenAdmin, OpenBoxoffice
from uobtheatre.users.models import User
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_user_schema(gql_client):
    user = gql_client.login().user

    # Create some booking
    bookings = [BookingFactory(user=user) for i in range(4)]

    # Create an irrelevant user with some bookings
    irrelevant_user = UserFactory()
    _ = [BookingFactory(user=irrelevant_user) for i in range(4)]

    response = gql_client.execute("""
        {
	      me {
            firstName
            lastName
            email
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
        """)

    assert list(user.bookings.all()) == bookings
    assert response == {
        "data": {
            "me": {
                "firstName": user.first_name,
                "lastName": user.last_name,
                "email": user.email,
                "id": to_global_id("UserNode", user.id),
                "bookings": {
                    "edges": [
                        {
                            "node": {
                                "id": to_global_id("BookingNode", booking.id)
                            }
                        }
                        for booking in bookings
                    ]
                },
            }
        }
    }


@pytest.mark.django_db
def test_user_schema_unauthenticated(gql_client):
    gql_client.logout()
    response = gql_client.execute("""
        {
	  me {
            email
          }
        }
        """)

    assert response == {"data": {"me": None}}


@override_settings(TURNSTILE_SECRET="1x0000000000000000000000000000000AA")
@pytest.mark.django_db
def test_user_field_error(gql_client):
    UserFactory()
    response = gql_client.execute("""
        mutation {
          register(
            email: "test@email.com"
            password1: "strongpassword"
            password2: "notsostrongpassword"
            firstName: "Tom"
            lastName: "Streuli"
            turnstileToken: "XXXX.DUMMY.TOKEN.XXXX"
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
        """)

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


@override_settings(TURNSTILE_SECRET="2x0000000000000000000000000000000AA")
@pytest.mark.django_db
def test_turnstile_rejection(gql_client):
    UserFactory()
    response = gql_client.execute("""
        mutation {
          register(
            email: "test@email.com"
            password1: "strongpassword"
            password2: "strongpassword"
            firstName: "Alex"
            lastName: "Streuli"
            turnstileToken: "XXXX.DUMMY.TOKEN.XXXX"
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
        """)

    assert response == {
        "data": {
            "register": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "invalid-input-response",
                        "field": "FieldErrors",
                        "code": "turnstileTokenReject",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_user_wrong_credentials(gql_client):
    response = gql_client.execute("""
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
        """)
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


@override_settings(TURNSTILE_SECRET="1x0000000000000000000000000000000AA")
@pytest.mark.django_db
def test_user_register(gql_client):
    # Create an account
    response = gql_client.execute("""
        mutation {
          register(
            email: "test@email.com"
            password1: "strongpassword"
            password2: "strongpassword"
            firstName: "James"
            lastName: "Tooof"
            turnstileToken: "XXXX.DUMMY.TOKEN.XXXX"
          ) {
            success
          }
        }
        """)

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
    assert (
        isinstance(response_data["token"], str)
        and len(response_data["token"]) > 150
    )
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
        response = gql_client.execute("""
            {
	          me {
                permissions
              }
            }
            """)

    mock_open_boxoffice.assert_called_once_with(gql_client.user)
    mock_open_admin.assert_called_once_with(gql_client.user)
    permissions = response["data"]["me"]["permissions"]
    assert ("boxoffice_open" in permissions) == user_can_open_boxoffice
    assert ("admin_open" in permissions) == user_can_open_admin


REGISTER_MUTATION = """
    mutation {
      register(
        email: "%s"
        password1: "strongpassword"
        password2: "strongpassword"
        firstName: "Mike"
        lastName: "Smith"
        turnstileToken: "XXXX.DUMMY.TOKEN.XXXX"
      ) {
        success
      }
    }
    """

LOGIN_MUTATION = """
    mutation {
      login(email: "%s", password: "%s") {
        success
        user {
          email
        }
      }
    }
    """

SECONDARY_EMAIL_MUTATION = """
    mutation {
      sendSecondaryEmailActivation(email: "%s", password: "strongpassword") {
        success
      }
    }
    """


def make_verified_user(email, password="strongpassword", **kwargs):
    """Make a verified user that can log in with the given password"""
    user = UserFactory(email=email, **kwargs)
    user.set_password(password)
    user.save()
    user.status.verified = True
    user.status.save()
    return user


@override_settings(TURNSTILE_SECRET="1x0000000000000000000000000000000AA")
@pytest.mark.django_db
def test_register_stores_email_in_lower_case(gql_client):
    response = gql_client.execute(REGISTER_MUTATION % "Mike@Example.com")

    assert response["data"]["register"]["success"] is True
    assert User.objects.get(first_name="Mike").email == "mike@example.com"


@override_settings(TURNSTILE_SECRET="1x0000000000000000000000000000000AA")
@pytest.mark.django_db
def test_register_rejects_email_that_only_differs_by_case(gql_client):
    first = gql_client.execute(REGISTER_MUTATION % "Mike@example.com")
    second = gql_client.execute(REGISTER_MUTATION % "mike@example.com")

    assert first["data"]["register"]["success"] is True
    assert second["data"]["register"]["success"] is False
    assert User.objects.filter(email__iexact="mike@example.com").count() == 1


@override_settings(TURNSTILE_SECRET="1x0000000000000000000000000000000AA")
@pytest.mark.django_db
def test_register_rejects_case_variant_of_existing_mixed_case_email(
    gql_client,
):
    # Accounts made before emails were lower cased keep the case they were typed in
    UserFactory(email="Mike@example.com")

    response = gql_client.execute(REGISTER_MUTATION % "mike@example.com")

    assert response["data"]["register"]["success"] is False
    assert User.objects.filter(email__iexact="mike@example.com").count() == 1


@pytest.mark.django_db
def test_login_ignores_email_case(gql_client):
    make_verified_user("mike@example.com")

    response = gql_client.execute(
        LOGIN_MUTATION % ("Mike@Example.com", "strongpassword")
    )

    assert response["data"]["login"]["success"] is True
    assert response["data"]["login"]["user"]["email"] == "mike@example.com"


@pytest.mark.django_db
def test_login_prefers_exact_email_match(gql_client):
    # Two old accounts that only differ by case. A case-insensitive lookup on
    # its own would find the one with the lower id first.
    make_verified_user("mike@example.com", "password-one", id=uuid.UUID(int=1))
    make_verified_user("Mike@example.com", "password-two", id=uuid.UUID(int=2))

    response = gql_client.execute(
        LOGIN_MUTATION % ("Mike@example.com", "password-two")
    )

    assert response["data"]["login"]["success"] is True
    assert response["data"]["login"]["user"]["email"] == "Mike@example.com"


@pytest.mark.django_db
def test_password_reset_email_ignores_email_case(gql_client, mailoutbox):
    UserFactory(email="mike@example.com")

    response = gql_client.execute("""
        mutation {
          sendPasswordResetEmail(email: "Mike@Example.com") {
            success
          }
        }
        """)

    assert response["data"]["sendPasswordResetEmail"]["success"] is True
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_secondary_email_activation_lower_cases_email(gql_client, mailoutbox):
    gql_client.login(make_verified_user("mike@example.com"))

    response = gql_client.execute(
        SECONDARY_EMAIL_MUTATION % "Mike.New@Example.com"
    )

    assert response["data"]["sendSecondaryEmailActivation"]["success"] is True
    assert mailoutbox[0].to == ["mike.new@example.com"]


@pytest.mark.django_db
def test_secondary_email_activation_rejects_case_variant_of_used_email(
    gql_client, mailoutbox
):
    UserFactory(email="taken@example.com")
    gql_client.login(make_verified_user("mike@example.com"))

    response = gql_client.execute(
        SECONDARY_EMAIL_MUTATION % "Taken@Example.com"
    )

    assert response["data"]["sendSecondaryEmailActivation"]["success"] is False
    assert len(mailoutbox) == 0
