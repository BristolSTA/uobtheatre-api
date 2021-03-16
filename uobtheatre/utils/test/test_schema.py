import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.utils.schema import IdInputField
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_graphene_image_mixin(gql_client, gql_id):
    venues = [VenueFactory() for i in range(2)]

    # Set one of the venues to have no image
    venues[1].image = None
    venues[1].save()

    response = gql_client.execute(
        """
        {
          venues {
            edges {
              node {
                image {
                  url
                }
              }
            }
          }
        }
        """
    )

    assert response == {
        "data": {
            "venues": {
                "edges": [
                    {
                        "node": {
                            "image": None
                            if not venue.image
                            else {"url": venue.image.url},
                        }
                    }
                    for venue in venues
                ]
            }
        }
    }


@pytest.mark.django_db
def test_id_input_field_wrong_thing(gql_client, gql_id):
    assert IdInputField.parse_literal(1.2) is None


@pytest.mark.django_db
def test_auth_required_mixin(gql_client_flexible, gql_id):
    booking = BookingFactory()
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
