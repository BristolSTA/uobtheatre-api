import pytest

from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
def test_venues_schema(gql_client, gql_id):
    venues = [VenueFactory() for i in range(3)]
    venue_performances = [
        [PerformanceFactory(venue=venue) for i in range(10)] for venue in venues
    ]

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
                performances {
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
                            "performances": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": gql_id(
                                                performance.id, "PerformanceNode"
                                            )
                                        }
                                    }
                                    for performance in venue_performances[index]
                                ]
                            },
                        }
                    }
                    for index, venue in enumerate(venues)
                ]
            }
        }
    }
