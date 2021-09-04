import datetime
import math

import pytest
from django.utils import timezone
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
)
from uobtheatre.discounts.test.factories import (
    DiscountFactory,
    DiscountRequirementFactory,
)
from uobtheatre.productions.models import Performance, Production
from uobtheatre.productions.test.factories import (
    AudienceWarningFactory,
    CastMemberFactory,
    CrewMemberFactory,
    PerformanceFactory,
    ProductionFactory,
    ProductionTeamMemberFactory,
    create_production,
)


@pytest.mark.django_db
def test_productions_schema(gql_client):

    production = ProductionFactory()
    performances = [PerformanceFactory(production=production) for i in range(2)]

    warnings = [AudienceWarningFactory() for i in range(3)]
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
                createdAt
                updatedAt
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
                isBookable
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
                start
                end
                minSeatPrice
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
                    department {
                      value
                      description
                    }
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
                  description
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
                            "createdAt": production.created_at.isoformat(),
                            "updatedAt": production.updated_at.isoformat(),
                            "ageRating": production.age_rating,
                            "coverImage": {"url": production.cover_image.file.url},
                            "description": production.description,
                            "facebookEvent": production.facebook_event,
                            "featuredImage": {
                                "url": production.featured_image.file.url,
                            },
                            "id": to_global_id("ProductionNode", production.id),
                            "isBookable": production.is_bookable(),
                            "name": production.name,
                            "posterImage": {
                                "url": production.poster_image.file.url,
                            },
                            "slug": production.slug,
                            "subtitle": production.subtitle,
                            "performances": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": to_global_id(
                                                "PerformanceNode", performance.id
                                            )
                                        }
                                    }
                                    for performance in performances
                                ],
                            },
                            "start": production.start_date().isoformat(),
                            "end": production.end_date().isoformat(),
                            "minSeatPrice": production.min_seat_price(),
                            "cast": [
                                {
                                    "id": to_global_id(
                                        "CastMemberNode", cast_member.id
                                    ),
                                    "name": cast_member.name,
                                    "profilePicture": {
                                        "url": cast_member.profile_picture.file.url
                                    }
                                    if cast_member.profile_picture
                                    else None,
                                    "role": cast_member.role,
                                    "production": {
                                        "id": to_global_id(
                                            "ProductionNode", production.id
                                        )
                                    },
                                }
                                for cast_member in cast
                            ],
                            "crew": [
                                {
                                    "id": to_global_id(
                                        "CrewMemberNode", crew_member.id
                                    ),
                                    "name": crew_member.name,
                                    "production": {
                                        "id": to_global_id(
                                            "ProductionNode", production.id
                                        )
                                    },
                                    "role": {
                                        "id": to_global_id(
                                            "CrewRoleNode", crew_member.role.id
                                        ),
                                        "name": crew_member.role.name,
                                        "department": {
                                            "value": str(
                                                crew_member.role.department
                                            ).upper(),
                                            "description": crew_member.role.get_department_display(),
                                        },
                                    },
                                }
                                for crew_member in crew
                            ],
                            "productionTeam": [
                                {
                                    "id": to_global_id(
                                        "ProductionTeamMemberNode",
                                        production_team_member.id,
                                    ),
                                    "name": production_team_member.name,
                                    "role": production_team_member.role,
                                    "production": {
                                        "id": to_global_id(
                                            "ProductionNode", production.id
                                        )
                                    },
                                }
                                for production_team_member in production_team
                            ],
                            "warnings": [
                                {
                                    "id": to_global_id("WarningNode", warning.id),
                                    "description": warning.description,
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


@pytest.mark.django_db
def test_performance_schema(gql_client):
    performances = [PerformanceFactory() for i in range(1)]

    response = gql_client.execute(
        """
        {
	  performances {
            edges {
              node {
                createdAt
                updatedAt
                capacity
                description
                disabled
                discounts {
                    id
                }
                doorsOpen
                durationMins
                end
                extraInformation
                id
                isOnline
                isInperson
                production {
                  id
                }
                start
                capacityRemaining
                venue {
                  id
                }
                minSeatPrice
                soldOut
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
                            "createdAt": performance.created_at.isoformat(),
                            "updatedAt": performance.updated_at.isoformat(),
                            "capacity": performance.capacity,
                            "description": performance.description,
                            "disabled": performance.disabled,
                            "discounts": [
                                {
                                    "id": to_global_id("DiscountNode", discount.id),
                                }
                                for discount in performance.discounts.all()
                            ],
                            "doorsOpen": performance.doors_open.isoformat(),
                            "durationMins": performance.duration().seconds // 60,
                            "end": performance.end.isoformat(),
                            "extraInformation": performance.extra_information,
                            "id": to_global_id("PerformanceNode", performance.id),
                            "isOnline": False,
                            "isInperson": True,
                            "production": {
                                "id": to_global_id(
                                    "ProductionNode", performance.production.id
                                )
                            },
                            "start": performance.start.isoformat(),
                            "capacityRemaining": performance.capacity_remaining(),
                            "venue": {
                                "id": to_global_id("VenueNode", performance.venue.id)
                            },
                            "minSeatPrice": performance.min_seat_price(),
                            "soldOut": performance.is_sold_out(),
                        }
                    }
                    for performance in performances
                ]
            }
        }
    }


@pytest.mark.skip(
    "TODO, start adding tests like this to check things that should be blocked"
)
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
def test_ticket_breakdown(gql_client):
    performance = PerformanceFactory()

    # Create a seat group with capacity of 50
    performance_seat_group = PerformanceSeatingFactory(
        performance=performance, capacity=50
    )

    # Create booking
    booking = BookingFactory(performance=performance)

    # Create two tickets
    TicketFactory(
        booking=booking, seat_group=performance_seat_group.seat_group, checked_in=True
    )
    TicketFactory(
        booking=booking, seat_group=performance_seat_group.seat_group, checked_in=False
    )

    response = gql_client.execute(
        """
        {
            performance(id: "%s") {
                ticketsBreakdown {
                    totalCapacity
                    totalSeatGroupCapacity
                    totalTicketsSold
                    totalTicketsCheckedIn
                    totalTicketsToCheckIn
                    totalTicketsAvailable
                }
            }
        }
        """
        % to_global_id("PerformanceNode", performance.id)
    )
    assert response == {
        "data": {
            "performance": {
                "ticketsBreakdown": {
                    "totalCapacity": 50,
                    "totalSeatGroupCapacity": 50,
                    "totalTicketsSold": 2,
                    "totalTicketsCheckedIn": 1,
                    "totalTicketsToCheckIn": 1,
                    "totalTicketsAvailable": 48,
                }
            }
        },
    }


@pytest.mark.django_db
def test_tickets_breakdown(gql_client):
    performance = PerformanceFactory()

    # Create some seat groups for this performance
    performance_seat_group_1 = PerformanceSeatingFactory(performance=performance)
    performance_seat_group_2 = PerformanceSeatingFactory(performance=performance)

    # Create a discount
    discount_1 = DiscountFactory(name="Family", percentage=0.2)
    discount_1.performances.set([performance])
    discount_requirement_1 = DiscountRequirementFactory(discount=discount_1, number=1)

    # Create a different
    discount_2 = DiscountFactory(name="Family 2", percentage=0.3)
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
                    concessionType {
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
                                            "concessionType": {
                                                "id": to_global_id(
                                                    "ConcessionTypeNode",
                                                    discount_requirement_1.concession_type.id,
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
                                            "concessionType": {
                                                "id": to_global_id(
                                                    "ConcessionTypeNode",
                                                    discount_requirement_2.concession_type.id,
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
                                        "id": to_global_id(
                                            "SeatGroupNode",
                                            performance_seat_group_1.seat_group.id,
                                        )
                                    },
                                },
                                {
                                    "capacityRemaining": performance.capacity_remaining(
                                        performance_seat_group_2.seat_group
                                    ),
                                    "concessionTypes": [
                                        {
                                            "concessionType": {
                                                "id": to_global_id(
                                                    "ConcessionTypeNode",
                                                    discount_requirement_1.concession_type.id,
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
                                            "concessionType": {
                                                "id": to_global_id(
                                                    "ConcessionTypeNode",
                                                    discount_requirement_2.concession_type.id,
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
                                        "id": to_global_id(
                                            "SeatGroupNode",
                                            performance_seat_group_2.seat_group.id,
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


@pytest.mark.django_db
def test_production_single_slug(gql_client):
    productions = [ProductionFactory() for i in range(2)]

    request = """
        query {
	  production(slug:"%s") {
            id
          }
        }

        """
    response = gql_client.execute(request % "")

    assert not response.get("errors", None)
    assert response["data"] == {"production": None}

    response = gql_client.execute(request % productions[0].slug)
    assert response["data"] == {
        "production": {"id": to_global_id("ProductionNode", productions[0].id)}
    }


@pytest.mark.django_db
def test_performance_single_id(gql_client):
    performances = [PerformanceFactory() for i in range(2)]

    request = """
        query {
	  performance(id: "%s") {
            id
          }
        }

        """

    # Ask for nothing and check you get nothing
    response = gql_client.execute(request % "")
    assert response["data"]["performance"] is None

    # Ask for first performance and check you get it
    response = gql_client.execute(
        request % to_global_id("PerformanceNode", performances[0].id)
    )
    assert response["data"] == {
        "performance": {"id": to_global_id("PerformanceNode", performances[0].id)}
    }


@pytest.mark.django_db
def test_upcoming_productions(gql_client):
    def create_prod(start, end):
        production = ProductionFactory()
        diff = end - start
        for i in range(5):
            time = start + (diff / 5) * i
            PerformanceFactory(start=time, end=time, production=production)
        return production

    current_time = timezone.now()
    # Create some producitons in the past
    for _ in range(10):
        create_prod(
            start=current_time - datetime.timedelta(days=11),
            end=current_time - datetime.timedelta(days=1),
        )

    # Create some prodcution going on right now
    productions = [
        create_production(
            start=current_time - datetime.timedelta(days=i),
            end=current_time + datetime.timedelta(days=i),
        )
        for i in range(1, 11)
    ]

    # Check we get 6 of the upcoming productions back in the right order
    request = """
        {
          productions(end_Gte: "%s", first: 6, orderBy: "end") {
            edges {
              node {
                end
              }
            }
          }
        }
        """

    # Ask for nothing and check you get nothing
    response = gql_client.execute(request % current_time.isoformat())
    assert response["data"]["productions"] == {
        "edges": [
            {"node": {"end": productions[i].end_date().isoformat()}} for i in range(6)
        ]
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "order_by, expected_order",
    [
        ("start", [0, 1, 2, 3]),
        ("-start", [3, 2, 1, 0]),
        ("end", [0, 1, 3, 2]),
        ("-end", [2, 3, 1, 0]),
    ],
)
def test_productions_orderby(order_by, expected_order, gql_client):
    current_time = timezone.now()

    productions = [
        create_production(
            start=current_time + datetime.timedelta(days=1),
            end=current_time + datetime.timedelta(days=1),
            production_id=0,
        ),
        create_production(
            start=current_time + datetime.timedelta(days=2),
            end=current_time + datetime.timedelta(days=2),
            production_id=1,
        ),
        create_production(
            start=current_time + datetime.timedelta(days=3),
            end=current_time + datetime.timedelta(days=6),
            production_id=2,
        ),
        create_production(
            start=current_time + datetime.timedelta(days=4),
            end=current_time + datetime.timedelta(days=5),
            production_id=3,
        ),
    ]
    request = """
        {
          productions(orderBy: "%s") {
            edges {
              node {
                end
              }
            }
          }
        }
        """

    # Ask for nothing and check you get nothing
    response = gql_client.execute(request % order_by)
    assert response["data"]["productions"]["edges"] == [
        {"node": {"end": productions[i].end_date().isoformat()}} for i in expected_order
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filter_name, value_days, expected_outputs",
    [
        ("start_Gte", 2, [2, 3]),
        ("start_Lte", 2, [0, 1, 2]),
        ("end_Gte", 2, [2, 3]),
        ("end_Lte", 2, [0, 1]),
    ],
)
def test_production_filters(filter_name, value_days, expected_outputs, gql_client):
    current_time = timezone.now()

    productions = [
        create_production(
            start=current_time + datetime.timedelta(days=0),
            end=current_time + datetime.timedelta(days=0),
            production_id=0,
        ),
        create_production(
            start=current_time + datetime.timedelta(days=1),
            end=current_time + datetime.timedelta(days=1),
            production_id=1,
        ),
        create_production(
            start=current_time + datetime.timedelta(days=2),
            end=current_time + datetime.timedelta(days=5),
            production_id=2,
        ),
        create_production(
            start=current_time + datetime.timedelta(days=3),
            end=current_time + datetime.timedelta(days=4),
            production_id=3,
        ),
    ]
    # Check we get 6 of the upcoming productions back in the right order
    request = """
        {
          productions(%s: "%s") {
            edges {
              node {
                end
              }
            }
          }
        }
        """

    # Ask for nothing and check you get nothing
    response = gql_client.execute(
        request
        % (
            filter_name,
            (current_time + datetime.timedelta(days=value_days)).isoformat(),
        )
    )
    assert response["data"]["productions"]["edges"] == [
        {"node": {"end": productions[i].end_date().isoformat()}}
        for i in expected_outputs
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "logged_in",
    [(True), (False)],
)
def test_draft_productions_not_shown_publically(logged_in, gql_client):
    _ = [ProductionFactory() for _ in range(3)]
    draft_production = ProductionFactory(status=Production.Status.DRAFT)

    request = """
        {
          productions {
            edges {
              node {
                id
              }
            }
          }
        }
        """
    if logged_in:
        gql_client.login()
    response = gql_client.execute(request)

    assert len(response["data"]["productions"]["edges"]) == 3
    assert draft_production.id not in [
        edge["node"]["id"] for edge in response["data"]["productions"]["edges"]
    ]


@pytest.mark.django_db
def test_draft_production_shown_with_permission(gql_client):
    _ = [ProductionFactory() for _ in range(3)]
    draft_production = ProductionFactory(status=Production.Status.DRAFT)
    assign_perm("production.edit", gql_client.login().user, draft_production)

    request = """
        {
          productions {
            edges {
              node {
                id
              }
            }
          }
        }
        """
    response = gql_client.execute(request)

    assert len(response["data"]["productions"]["edges"]) == 4


@pytest.mark.django_db
def test_performance_run_on(gql_client):
    query_date = datetime.date(year=2000, month=6, day=20)
    _ = [
        PerformanceFactory(
            start=query_date + timezone.timedelta(days=i),
            end=query_date + timezone.timedelta(days=i, hours=2),
        )
        for i in range(-2, 2)
    ]

    # Check we get 6 of the upcoming productions back in the right order
    request = """
        {
          performances(runOn: "%s") {
            edges {
              node {
                start
              }
            }
          }
        }
        """

    # Ask for nothing and check you get nothing
    response = gql_client.execute(request % query_date)
    assert response["data"]["performances"]["edges"] == [
        {"node": {"start": perm.start.isoformat()}}
        for perm in Performance.objects.running_on(query_date)
    ]


@pytest.mark.django_db
def test_performance_has_permission(gql_client):
    performances = [PerformanceFactory() for _ in range(3)]

    assign_perm("boxoffice", gql_client.user, performances[0].production)

    # Check we get 6 of the upcoming productions back in the right order
    request = """
        {
          performances(hasBoxofficePermissions: %s) {
            edges {
              node {
                id
              }
            }
          }
        }
        """

    # Ask for nothing and check you get nothing
    response = gql_client.execute(request % "true")
    assert response["data"]["performances"]["edges"] == [
        {"node": {"id": to_global_id("PerformanceNode", perm.id)}}
        for perm in performances[:1]
    ]

    response = gql_client.execute(request % "false")
    assert response["data"]["performances"]["edges"] == [
        {"node": {"id": to_global_id("PerformanceNode", perm.id)}}
        for perm in performances[1:]
    ]
