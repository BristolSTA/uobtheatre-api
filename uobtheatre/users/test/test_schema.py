import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_user_schema(gql_client_flexible, gql_id):

    user = gql_client_flexible.request_factory.user

    # Create some booking
    bookings = [BookingFactory(user=user) for i in range(4)]

    # Create an irrelevant user with some bookings
    # irrelevant_user = UserFactory()
    # _ = [BookingFactory(user=irrelevant_user) for i in range(4)]

    response = gql_client_flexible.execute(
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
                "id": gql_id(user.id, "UserNode"),
                "bookings": {
                    "edges": [
                        {"node": {"id": gql_id(booking.id, "BookingNode")}}
                        for booking in bookings
                    ]
                },
            }
        }
    }


@pytest.mark.django_db
def test_user_schema_unauthenticated(gql_client_flexible):
    gql_client_flexible.logout()
    response = gql_client_flexible.execute(
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
def test_user_field_error(gql_client_flexible):
    UserFactory()
    response = gql_client_flexible.execute(
        """
        mutation {
          register(
            email: "test@email.com"
            password1: "strongpassword"
            password2: "notsostrongpassword"
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
            token
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
                "token": None,
            }
        }
    }


@pytest.mark.django_db
def test_user_wrong_credentials(gql_client_flexible):
    response = gql_client_flexible.execute(
        """
        mutation {
          tokenAuth(email:"fakeaccount@email.com", password:"strongpassword"){
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
            "tokenAuth": {
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
