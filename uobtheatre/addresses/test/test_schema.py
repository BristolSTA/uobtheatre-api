import pytest

# from uobtheatre.addresses.test.factories import PerformanceFactory
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_address_schema(gql_client, gql_id):
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
                            "id": gql_id(venue.id, "VenueNode"),
                            "address": {
                                "id": gql_id(venue.address.id, "AddressNode"),
                                "buildingName": venue.address.building_name,
                                "buildingNumber": venue.address.building_number,
                                "street": venue.address.street,
                                "city": venue.address.city,
                                "postcode": venue.address.postcode,
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
