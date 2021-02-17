import pytest

from uobtheatre.bookings.test.factories import BookingFactory


@pytest.mark.django_db
def test_user_schema(gql_client_flexible, gql_id):

    response = gql_client_flexible.execute(
        """
        {
	  authUser {
            username
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

    user = gql_client_flexible.request_factory.user

    # Create some booking
    bookings = [BookingFactory(user=user) for i in range(4)]

    # Create an irrelevant user with some bookings
    # irrelevant_user = UserFactory()
    # _ = [BookingFactory(user=irrelevant_user) for i in range(4)]

    assert list(user.bookings.all()) == bookings
    assert response == {
        "data": {
            "authUser": {
                "username": user.username,
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
