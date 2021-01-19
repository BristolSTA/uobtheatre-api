import pytest

from uobtheatre.bookings.test.factories import BookingFactory


@pytest.mark.django_db
def test_bookings_schema(gql_client):

    booking = BookingFactory()
    response = gql_client.execute(
        """
        {
            bookings {
                id
            }
        }
        """,
        context={"user": booking.user},
    )

    assert response == {}
