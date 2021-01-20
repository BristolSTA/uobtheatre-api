import pytest

from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_venues_schema(gql_client, gql_id):
    venues = [VenueFactory() for i in range(3)]

    response = gql_client.execute(
        """
        {
          venues {
            edges {
              node {
                id
                name
                internalCapacity
                description
                image {
                  url
                }
                publiclyListed
                slug
                seatGroups {
                  edges {
                    node {
                      id
                    }
                  }
                }
                performanceSet {
                  edges {
                    node {
                      id
                    }
                  }
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
                            "name": venue.name,
                            "internalCapacity": venue.internal_capacity,
                            "description": venue.description,
                            "image": {"url": venue.image.url},
                            "publiclyListed": venue.publicly_listed,
                            "slug": venue.slug,
                            "seatGroups": {"edges": []},
                            "performanceSet": {"edges": []},
                        }
                    }
                    for venue in venues
                ]
            }
        }
    }
