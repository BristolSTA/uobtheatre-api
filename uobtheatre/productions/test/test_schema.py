import math

import pytest

from uobtheatre.bookings.test.factories import (
    DiscountFactory,
    DiscountRequirementFactory,
    PerformanceSeatingFactory,
)
from uobtheatre.productions.test.factories import (
    CastMemberFactory,
    CrewMemberFactory,
    PerformanceFactory,
    ProductionFactory,
    ProductionTeamMemberFactory,
    WarningFactory,
)


@pytest.mark.django_db
def test_productions_schema(gql_client, gql_id):

    production = ProductionFactory()
    performances = [PerformanceFactory(production=production) for i in range(2)]

    warnings = [WarningFactory() for i in range(3)]
    production.warnings.set(warnings)

    cast = [CastMemberFactory(production=production) for i in range(10)]
    crew = [CrewMemberFactory(production=production) for i in range(10)]
    production_team = [
        ProductionTeamMemberFactory(production=production) for i in range(10)
    ]

    response = gql_client.execute(
        """
        {
	  productions {
            edges {
              node {
                ageRating
                coverImage {
                  url
                }
                description
                facebookEvent
                featuredImage {
                  url
                }
                id
                name
                posterImage {
                  url
                }
                slug
                subtitle
                performances {
                  edges {
                    node {
                      id
                    }
                  }
                }
                startDate
                endDate
                cast {
                  id
                  name
                  profilePicture {
                    url
                  }
                  role
                  production {
                    id
                  }
                }
                crew {
                  id
                  name
                  production {
                    id
                  }
                  role {
                    id
                    name
                    department
                  }
                }
                productionTeam {
                  id
                  name
                  role
                  production {
                    id
                  }
                }
                warnings {
                  id
                  warning
                }
              }
            }
          }
        }
        """
    )

    assert response == {
        "data": {
            "productions": {
                "edges": [
                    {
                        "node": {
                            "ageRating": production.age_rating,
                            "coverImage": {"url": production.cover_image.url},
                            "description": production.description,
                            "facebookEvent": production.facebook_event,
                            "featuredImage": {
                                "url": production.featured_image.url,
                            },
                            "id": gql_id(production.id, "ProductionNode"),
                            "name": production.name,
                            "posterImage": {
                                "url": production.poster_image.url,
                            },
                            "slug": production.slug,
                            "subtitle": production.subtitle,
                            "performances": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": gql_id(
                                                performance.id, "PerformanceNode"
                                            )
                                        }
                                    }
                                    for performance in performances
                                ],
                            },
                            "startDate": production.start_date().isoformat(),
                            "endDate": production.end_date().isoformat(),
                            "cast": [
                                {
                                    "id": gql_id(cast_member.id, "CastMemberNode"),
                                    "name": cast_member.name,
                                    "profilePicture": {
                                        "url": cast_member.profile_picture.url
                                    }
                                    if cast_member.profile_picture
                                    else None,
                                    "role": cast_member.role,
                                    "production": {
                                        "id": gql_id(production.id, "ProductionNode")
                                    },
                                }
                                for cast_member in cast
                            ],
                            "crew": [
                                {
                                    "id": gql_id(crew_member.id, "CrewMemberNode"),
                                    "name": crew_member.name,
                                    "production": {
                                        "id": gql_id(production.id, "ProductionNode")
                                    },
                                    "role": {
                                        "id": gql_id(
                                            crew_member.role.id, "CrewRoleNode"
                                        ),
                                        "name": crew_member.role.name,
                                        "department": str(
                                            crew_member.role.department
                                        ).upper(),
                                    },
                                }
                                for crew_member in crew
                            ],
                            "productionTeam": [
                                {
                                    "id": gql_id(
                                        production_team_member.id,
                                        "ProductionTeamMemberNode",
                                    ),
                                    "name": production_team_member.name,
                                    "role": production_team_member.role,
                                    "production": {
                                        "id": gql_id(production.id, "ProductionNode")
                                    },
                                }
                                for production_team_member in production_team
                            ],
                            "warnings": [
                                {
                                    "id": gql_id(warning.id, "WarningNode"),
                                    "warning": warning.warning,
                                }
                                for warning in warnings
                            ],
                        }
                    }
                ]
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "factories, requests",
    [
        # slug exact tests
        (
            [
                (ProductionFactory, {"slug": "not-example-show"}),
                (ProductionFactory, {"slug": "example-show"}),
            ],
            [('slug: "example-show"', 1), ('slug: "not-a-thing"', 0)],
        ),
        # pk exact test
        (
            [
                (ProductionFactory, {"id": 1}),
                (ProductionFactory, {"id": 2}),
            ],
            [
                ('id: "UHJvZHVjdGlvbk5vZGU6MQ=="', 1),
                ('id: "UHJvZHVjdGlvbk5vZGU6Mw=="', 0),
            ],
        ),
    ],
)
def test_productions_filter(factories, requests, gql_client):
    """
    factories - A list of tuples each tuple cosists of a factory and the
    parameters to use when calling that factory.
    requests - A list of tuples which contains a filter string and the number
    of expected productions to be returned when a query with that filter string
    is called.
    """

    # Create all the objects with the factories
    for fact in factories:
        factory, args = fact
        factory(**args)

    # Test all the requests return the correct number
    for request in requests:
        filter_args, expected_number = request

        query_string = "{ productions(" + filter_args + ") { edges { node { id } } } }"
        response = gql_client.execute(query_string)

        assert len(response["data"]["productions"]["edges"]) == expected_number


@pytest.mark.skip(reason="JamesToDO")
@pytest.mark.django_db
def test_performance_excludes(gql_client, gql_id):
    # excludes performance seat groups
    assert False


@pytest.mark.django_db
def test_performance_schema(gql_client, gql_id):
    performances = [PerformanceFactory() for i in range(1)]

    response = gql_client.execute(
        """
        {
	  performances {
            edges {
              node {
                capacity
                description
                disabled
                doorsOpen
                end
                extraInformation
                id
                production {
                  id
                }
                start
                capacityRemaining
                venue {
                  id
                }
              }
            }
          }
        }
        """
    )

    assert response == {
        "data": {
            "performances": {
                "edges": [
                    {
                        "node": {
                            "capacity": performance.capacity,
                            "description": performance.description,
                            "disabled": performance.disabled,
                            "doorsOpen": performance.doors_open.isoformat(),
                            "end": performance.end.isoformat(),
                            "extraInformation": performance.extra_information,
                            "id": gql_id(performance.id, "PerformanceNode"),
                            "production": {
                                "id": gql_id(
                                    performance.production.id, "ProductionNode"
                                )
                            },
                            "start": performance.start.isoformat(),
                            "capacityRemaining": performance.capacity_remaining(),
                            "venue": {"id": gql_id(performance.venue.id, "VenueNode")},
                        }
                    }
                    for performance in performances
                ]
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "attribute, is_obj",
    [
        ("bookings", True),
    ],
)
def test_performance_blocked_attributes(gql_client, attribute, is_obj):
    query_string = """
        {
            performances {
              edges {
                node {
                  %s
                }
              }
            }
        }
        """ % (
        attribute if not is_obj else "%s {id}" % attribute
    )

    response = gql_client.execute(query_string)
    assert (
        response["errors"][0]["message"]
        == f'Cannot query field "{attribute}" on type "PerformanceNode".'
    )


@pytest.mark.django_db
def test_ticket_options(gql_client, gql_id):
    performance = PerformanceFactory()

    # Create some seat groups for this performance
    performance_seat_group_1 = PerformanceSeatingFactory(performance=performance)
    performance_seat_group_2 = PerformanceSeatingFactory(performance=performance)

    # Create a discount
    discount_1 = DiscountFactory(name="Family", discount=0.2)
    discount_1.performances.set([performance])
    discount_requirement_1 = DiscountRequirementFactory(discount=discount_1, number=1)

    # Create a different
    discount_2 = DiscountFactory(name="Family 2", discount=0.3)
    discount_2.performances.set([performance])
    discount_requirement_2 = DiscountRequirementFactory(discount=discount_2, number=1)

    response = gql_client.execute(
        """
        {
          performances {
            edges {
              node {
              	ticketOptions {
                  capacityRemaining
                  seatGroup {
                    id
                  }
                  concessionTypes {
                    price
                    pricePounds
                    concession {
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
            "performances": {
                "edges": [
                    {
                        "node": {
                            "ticketOptions": [
                                {
                                    "capacityRemaining": performance.capacity_remaining(
                                        performance_seat_group_1.seat_group
                                    ),
                                    "concessionTypes": [
                                        {
                                            "concession": {
                                                "id": gql_id(
                                                    discount_requirement_1.concession_type.id,
                                                    "ConcessionTypeNode",
                                                ),
                                            },
                                            "price": math.ceil(
                                                0.8 * performance_seat_group_1.price
                                            ),
                                            "pricePounds": "%.2f"
                                            % (
                                                math.ceil(
                                                    0.8 * performance_seat_group_1.price
                                                )
                                                / 100
                                            ),
                                        },
                                        {
                                            "concession": {
                                                "id": gql_id(
                                                    discount_requirement_2.concession_type.id,
                                                    "ConcessionTypeNode",
                                                ),
                                            },
                                            "price": math.ceil(
                                                0.7 * performance_seat_group_1.price
                                            ),
                                            "pricePounds": "%.2f"
                                            % (
                                                math.ceil(
                                                    0.7 * performance_seat_group_1.price
                                                )
                                                / 100
                                            ),
                                        },
                                    ],
                                    "seatGroup": {
                                        "id": gql_id(
                                            performance_seat_group_1.seat_group.id,
                                            "SeatGroupNode",
                                        )
                                    },
                                },
                                {
                                    "capacityRemaining": performance.capacity_remaining(
                                        performance_seat_group_2.seat_group
                                    ),
                                    "concessionTypes": [
                                        {
                                            "concession": {
                                                "id": gql_id(
                                                    discount_requirement_1.concession_type.id,
                                                    "ConcessionTypeNode",
                                                ),
                                            },
                                            "price": math.ceil(
                                                0.8 * performance_seat_group_2.price
                                            ),
                                            "pricePounds": "%.2f"
                                            % (
                                                math.ceil(
                                                    0.8 * performance_seat_group_2.price
                                                )
                                                / 100
                                            ),
                                        },
                                        {
                                            "concession": {
                                                "id": gql_id(
                                                    discount_requirement_2.concession_type.id,
                                                    "ConcessionTypeNode",
                                                ),
                                            },
                                            "price": math.ceil(
                                                0.7 * performance_seat_group_2.price
                                            ),
                                            "pricePounds": "%.2f"
                                            % (
                                                math.ceil(
                                                    0.7 * performance_seat_group_2.price
                                                )
                                                / 100
                                            ),
                                        },
                                    ],
                                    "seatGroup": {
                                        "id": gql_id(
                                            performance_seat_group_2.seat_group.id,
                                            "SeatGroupNode",
                                        )
                                    },
                                },
                            ]
                        }
                    }
                ]
            }
        },
    }
