import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_address_schema(gql_client):
    venues = [VenueFactory() for i in range(3)]

    response = gql_client.execute(
        """
        {
          venues {
            edges {
              node {
                id
                address {
                  id
                  buildingName
                  buildingNumber
                  street
                  city
                  postcode
                  what3words
                  latitude
                  longitude
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
                            "id": to_global_id("VenueNode", venue.id),
                            "address": {
                                "id": to_global_id("AddressNode", venue.address.id),
                                "buildingName": venue.address.building_name,
                                "buildingNumber": venue.address.building_number,
                                "street": venue.address.street,
                                "city": venue.address.city,
                                "postcode": venue.address.postcode,
                                "what3words": venue.address.what3words,
                                "latitude": float(venue.address.latitude),
                                "longitude": float(venue.address.longitude),
                            },
                        }
                    }
                    for index, venue in enumerate(venues)
                ]
            }
        }
    }
