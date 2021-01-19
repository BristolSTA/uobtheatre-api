import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory


@pytest.mark.django_db
def test_bookings_schema(gql_client_flexible, gql_id):

    booking = BookingFactory(status=Booking.BookingStatus.INPROGRESS)
    # Create a booking that is not owned by the same user
    BookingFactory(status=Booking.BookingStatus.INPROGRESS)

    request_query = """
        {
          bookings {
            edges {
              node {
                id
                bookingReference
                performance {
                  id
                }
                status
              }
            }
          }
        }
        """
    client = gql_client_flexible

    # When there is no user expect no bookings
    client.logout()
    response = client.execute(request_query)
    assert response == {"data": {"bookings": {"edges": []}}}

    # When we are logged in expect only the user's bookings
    client.set_user(booking.user)
    response = client.execute(request_query)
    assert response == {
        "data": {
            "bookings": {
                "edges": [
                    {
                        "node": {
                            "id": gql_id(booking.id, "BookingNode"),
                            "bookingReference": str(booking.booking_reference),
                            "performance": {
                                "id": gql_id(booking.performance.id, "PerformanceNode")
                            },
                            "status": "IN_PROGRESS",
                        }
                    }
                ]
            }
        }
    }
