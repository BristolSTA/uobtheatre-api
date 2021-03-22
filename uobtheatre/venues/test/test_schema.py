import pytest

from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.venues.test.factories import SeatGroupFactory, VenueFactory


@pytest.mark.django_db
def test_venues_schema(gql_client, gql_id):
    venues = [VenueFactory() for i in range(3)]
    venue_performances = [
        [PerformanceFactory(venue=venue) for i in range(10)] for venue in venues
    ]
    venue_seat_groups = [
        [SeatGroupFactory(venue=venue) for i in range(10)] for venue in venues
    ]

    response = gql_client.execute(
        """
        {
          venues {
            edges {
              node {
                id
                createdAt
                updatedAt
                name
                address {
                  id
                }
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
                productions {
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
                            "createdAt": venue.created_at.isoformat(),
                            "updatedAt": venue.updated_at.isoformat(),
                            "name": venue.name,
                            "address": {
                                "id": gql_id(venue.address.id, "AddressNode"),
                            },
                            "internalCapacity": venue.internal_capacity,
                            "description": venue.description,
                            "image": {"url": venue.image.file.url},
                            "publiclyListed": venue.publicly_listed,
                            "slug": venue.slug,
                            "seatGroups": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": gql_id(seat_group.id, "SeatGroupNode")
                                        }
                                    }
                                    for seat_group in venue_seat_groups[index]
                                ]
                            },
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
                            "productions": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": gql_id(
                                                production.id, "ProductionNode"
                                            )
                                        }
                                    }
                                    for production in venue.get_productions()
                                ]
                            },
                        }
                    }
                    for index, venue in enumerate(venues)
                ]
            }
        }
    }


@pytest.mark.django_db
def test_slug_single_schema(gql_client, gql_id):
    venues = [VenueFactory() for i in range(2)]

    request = """
        query {
	  venue(slug:"%s") {
            id
          }
        }

        """
    response = gql_client.execute(request % "")

    assert response["errors"][0]["message"] == "Venue matching query does not exist."
    assert response["data"] == {"venue": None}

    response = gql_client.execute(request % venues[0].slug)
    assert response["data"] == {"venue": {"id": gql_id(venues[0].id, "VenueNode")}}
