# pylint: disable=too-many-lines
import datetime
import math

import pytest
import pytz
from django.utils import timezone
from graphql_relay.node.node import from_global_id, to_global_id
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
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.productions.models import Performance, Production
from uobtheatre.productions.test.factories import (
    CastMemberFactory,
    ContentWarningFactory,
    CrewMemberFactory,
    PerformanceFactory,
    ProductionFactory,
    ProductionTeamMemberFactory,
    create_production,
)
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import VenueFactory

###
# Production Queries
###


@pytest.mark.django_db
def test_productions_schema(gql_client):
    production = ProductionFactory()
    performances = [PerformanceFactory(production=production) for i in range(2)]

    warnings = [
        ContentWarningFactory(short_description="A"),
        ContentWarningFactory(short_description="B"),
        ContentWarningFactory(short_description="C"),
    ]
    production.content_warnings.set(warnings)

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
                shortDescription
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
                contentWarnings {
                    information
                    warning {
                        id
                        shortDescription
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
                            "shortDescription": production.short_description,
                            "minSeatPrice": production.min_seat_price(),
                            "cast": [
                                {
                                    "id": to_global_id(
                                        "CastMemberNode", cast_member.id
                                    ),
                                    "name": cast_member.name,
                                    "profilePicture": (
                                        {"url": cast_member.profile_picture.file.url}
                                        if cast_member.profile_picture
                                        else None
                                    ),
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
                                        "department": str(
                                            crew_member.role.department
                                        ).upper(),
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
                            "contentWarnings": [
                                {
                                    "information": None,
                                    "warning": {
                                        "id": to_global_id(
                                            "ContentWarningNode", warning.id
                                        ),
                                        "shortDescription": warning.short_description,
                                    },
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
@pytest.mark.parametrize(
    "query_args, expected_production",
    [
        ('slug: "example-show"', 1),
        ('slug: "not-a-thing"', None),
        (f'id: "{to_global_id("ProductionNode", 1)}"', 1),
        (f'id: "{to_global_id("ProductionNode", 2)}"', 2),
        (f'id: "{to_global_id("ProductionNode", 3)}"', None),
        (f'id: "{to_global_id("ProductionNode", 1)}" slug: "example-show"', 1),
        (f'id: "{to_global_id("ProductionNode", 1)}" slug: "not-a-thing"', None),
        (None, None),
    ],
)
def test_resolve_production(gql_client, query_args, expected_production):
    ProductionFactory(slug="example-show", id=1)
    ProductionFactory(slug="other-show", id=2)

    request = """
      query {
	    production%s {
          id
        }
      }
    """
    response = gql_client.execute(request % (f"({query_args})" if query_args else ""))

    if expected_production is not None:
        assert response["data"]["production"]["id"] == to_global_id(
            "ProductionNode", expected_production
        )
    else:
        assert response["data"]["production"] is None


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
        ("start_Gte", 2, [3, 2]),
        ("start_Lte", 2, [0, 1, 2]),
        ("end_Gte", 2, [3, 2]),
        ("end_Lte", 2, [0, 1]),
    ],
)
def test_production_time_filters(filter_name, value_days, expected_outputs, gql_client):
    current_time = timezone.now().replace(microsecond=0, second=0)

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
          productions(%s: "%s", orderBy: "end") {
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
    "query,results",
    [
        ("trash", ["TRASh 2021"]),
        ("gin", ["Legally Ginger"]),
        ("Nothing", []),
        ("", ["TRASh 2021", "Legally Ginger"]),
    ],
)
def test_production_search_filter(gql_client, query, results):
    ProductionFactory(name="TRASh 2021")
    ProductionFactory(name="Legally Ginger")
    request = """
        {
          productions(search: "%s") {
            edges {
              node {
                name
              }
            }
          }
        }
        """

    response = gql_client.execute(request % query)
    assert len(response["data"]["productions"]["edges"]) == len(results)

    for result in results:
        assert {"node": {"name": result}} in response["data"]["productions"]["edges"]


@pytest.mark.django_db
def test_productions_are_shown_with_permission(gql_client):
    _ = [ProductionFactory() for _ in range(3)]
    draft_production = ProductionFactory(status=Production.Status.DRAFT, slug="my-show")
    assign_perm(
        "productions.view_production", gql_client.login().user, draft_production
    )

    request = """
        {
          productions {
            edges {
              node {
                id
              }
            }
          }
          production(slug: "my-show") {
              name
          }
        }
        """
    response = gql_client.execute(request)

    assert len(response["data"]["productions"]["edges"]) == 4
    assert response["data"]["production"] is not None


@pytest.mark.django_db
def test_production_and_performance_sales_breakdowns(gql_client):
    performance = PerformanceFactory()
    booking = BookingFactory(performance=performance, status=Payable.Status.IN_PROGRESS)
    perf_seat_group = PerformanceSeatingFactory(performance=performance, price=100)
    TicketFactory(booking=booking, seat_group=perf_seat_group.seat_group)
    TransactionFactory(
        pay_object=booking, value=booking.total, app_fee=0, provider_fee=0
    )

    request = """
        {
          productions(id: "%s") {
            edges {
                node {
                    salesBreakdown {
                        totalPayments
                        totalCardPayments
                        providerPaymentValue
                        appPaymentValue
                        societyTransferValue
                        societyRevenue
                    }
                    performances {
                        edges {
                            node {
                                salesBreakdown {
                                    totalPayments
                                    totalCardPayments
                                    providerPaymentValue
                                    appPaymentValue
                                    societyTransferValue
                                    societyRevenue
                                }
                            }
                        }
                    }
                }
            }
        }
        }
        """

    # First, test as unauthenticated/unauthorised
    user = UserFactory()
    gql_client.login(user)
    response = gql_client.execute(
        request % to_global_id("ProductionNode", performance.production.id)
    )
    assert response["data"]["productions"]["edges"][0]["node"]["salesBreakdown"] is None
    assert (
        response["data"]["productions"]["edges"][0]["node"]["performances"]["edges"][0][
            "node"
        ]["salesBreakdown"]
        is None
    )

    # Second, add permission to view sales for production
    assign_perm("sales", user, performance.production)
    response = gql_client.execute(
        request % to_global_id("ProductionNode", performance.production.id)
    )
    assert response["data"]["productions"]["edges"][0]["node"]["salesBreakdown"] == {
        "appPaymentValue": 0,
        "providerPaymentValue": 0,
        "societyRevenue": 100,
        "societyTransferValue": 100,
        "totalCardPayments": 100,
        "totalPayments": 100,
    }
    assert response["data"]["productions"]["edges"][0]["node"]["performances"]["edges"][
        0
    ]["node"]["salesBreakdown"] == {
        "appPaymentValue": 0,
        "providerPaymentValue": 0,
        "societyRevenue": 100,
        "societyTransferValue": 100,
        "totalCardPayments": 100,
        "totalPayments": 100,
    }


@pytest.mark.django_db
def test_production_totals(gql_client):
    # Create 2 performances for the same production
    perf_1 = PerformanceFactory(capacity=100)
    perf_2 = PerformanceFactory(production=perf_1.production, capacity=150)

    # Create 1 seat group for the first performance with 1000 seats
    PerformanceSeatingFactory(performance=perf_1, capacity=1000)

    # Create 1 seat group for the second performance with 140 seats
    PerformanceSeatingFactory(performance=perf_2, capacity=140)

    booking_1 = BookingFactory(performance=perf_1)
    TicketFactory(booking=booking_1)

    request = """
        {
          productions(id: "%s") {
            edges {
                node {
                    totalCapacity
                    totalTicketsSold
                }
            }
        }
        }
        """

    response = gql_client.login(user=UserFactory(is_superuser=True)).execute(
        request % to_global_id("ProductionNode", perf_1.production.id)
    )
    assert response["data"]["productions"]["edges"][0]["node"]["totalCapacity"] == 240
    assert response["data"]["productions"]["edges"][0]["node"]["totalTicketsSold"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "with_perm,users,expected_users",
    [
        (False, [], []),
        (False, [[], ["change_production"]], []),
        (True, [], []),
        (True, [[], ["change_production"]], [1]),
        (True, [[], ["change_production"], ["boxoffice"]], [1, 2]),
    ],
)
def test_production_assigned_users(gql_client, with_perm, users, expected_users):
    production = ProductionFactory(slug="my-production")
    request = """
        query {
            production(slug: "my-production") {
                assignedUsers {
                    user {
                        id
                    }
                    assignedPermissions
                }
            }
        }
    """

    user_models = []
    for permissions in users:
        user_model = UserFactory()
        user_models.append(user_model)
        for perm in permissions:
            assign_perm(perm, user_model, production)

    gql_client.login()
    if with_perm:
        assign_perm("change_production", gql_client.user, production)

    response = gql_client.execute(request)

    if not with_perm:
        assert response["data"]["production"]["assignedUsers"] is None
    else:
        present_users = [
            from_global_id(assignedUser["user"]["id"])[1]
            for assignedUser in response["data"]["production"]["assignedUsers"]
        ]

        for user_index in expected_users:
            # Check the user's ID is in the present users
            assert str(user_models[user_index].id) in present_users

            # Check that the permissions reported are equal to the expected permissions
            assert (
                response["data"]["production"]["assignedUsers"][
                    present_users.index(str(user_models[user_index].id))
                ]["assignedPermissions"]
                == users[user_index]
            )

        assert (
            str(gql_client.user.id) in present_users
        )  # They have been assigned change_production too!


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("perms", "can_assign", "expected_permissions", "expected_perm_count"),
    [
        ([], False, [], 0),
        (["boxoffice"], False, [], 0),
        (
            ["boxoffice", "change_production"],
            True,
            [
                "boxoffice",
                "view_production",
                "view_bookings",
                "change_production",
                "sales",
            ],
            6,
        ),
    ],
)
def test_assignable_permissions(
    gql_client, perms, can_assign, expected_permissions, expected_perm_count
):
    production = ProductionFactory(slug="my-production")
    gql_client.login()

    for perm in perms:
        assign_perm(perm, gql_client.user, production)

    request = """
        query {
            production(slug: "my-production") {
                assignablePermissions {
                    name
                    userCanAssign
                }
            }
        }
    """

    response = gql_client.execute(request)

    if can_assign is False:
        assert response["data"]["production"]["assignablePermissions"] is None
        return

    assert len(response["data"]["production"]["assignablePermissions"]) == 10

    assert (
        len(
            [
                perm
                for perm in response["data"]["production"]["assignablePermissions"]
                if perm["userCanAssign"]
            ]
        )
        == expected_perm_count
    )

    for perm in expected_permissions:
        assert {
            "name": perm,
            "userCanAssign": True,
        } in response["data"][
            "production"
        ]["assignablePermissions"]


@pytest.mark.django_db
def test_production_venues(gql_client):
    production = ProductionFactory()
    venue_1 = VenueFactory(name="Venue 1")
    venue_2 = VenueFactory(name="Venue 2")
    VenueFactory(name="Venue 3")

    PerformanceFactory(production=production, venue=venue_1)
    PerformanceFactory(production=production, venue=venue_1)
    PerformanceFactory(production=production, venue=venue_2)

    query = """
        query {
            production(id: "%s") {
                venues {
                    name
                }
            }
        }
    """

    response = gql_client.execute(
        query
        % to_global_id(
            "ProductionNode",
            production.id,
        )
    )

    assert response["data"]["production"] == {
        "venues": [{"name": "Venue 1"}, {"name": "Venue 2"}],
    }


###
# Performance Queries
###


@pytest.mark.django_db
def test_performance_schema(gql_client):
    performances = [
        PerformanceFactory(
            doors_open=datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=pytz.UTC),
            start=datetime.datetime(2020, 1, 1, 1, 0, 0, tzinfo=pytz.UTC),
            end=datetime.datetime(2020, 1, 2, 1, 0, 0, tzinfo=pytz.UTC),
        )
        for _ in range(1)
    ]

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
                  edges {
                    node {
                      id
                    }
                  }
                }
                doorsOpen
                durationMins
                end
                extraInformation
                id
                isOnline
                isInperson
                isBookable
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
                            "capacity": None,
                            "description": performance.description,
                            "disabled": False,
                            "discounts": {
                                "edges": [
                                    {
                                        "id": to_global_id("DiscountNode", discount.id),
                                    }
                                    for discount in performance.discounts.all()
                                ]
                            },
                            "doorsOpen": "2020-01-01T00:00:00+00:00",
                            "durationMins": 24 * 60,  # 1 day
                            "end": "2020-01-02T01:00:00+00:00",
                            "extraInformation": performance.extra_information,
                            "id": to_global_id("PerformanceNode", performance.id),
                            "isOnline": False,
                            "isInperson": True,
                            "production": {
                                "id": to_global_id(
                                    "ProductionNode", performance.production.id
                                )
                            },
                            "start": "2020-01-01T01:00:00+00:00",
                            "capacityRemaining": performance.capacity_remaining,
                            "venue": {
                                "id": to_global_id("VenueNode", performance.venue.id)
                            },
                            "minSeatPrice": performance.min_seat_price(),
                            "soldOut": performance.is_sold_out,
                            "isBookable": performance.is_bookable,
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
        booking=booking,
        seat_group=performance_seat_group.seat_group,
        set_checked_in=True,
    )
    TicketFactory(
        booking=booking,
        seat_group=performance_seat_group.seat_group,
        set_checked_in=False,
    )

    response = gql_client.execute(
        """
        {
            performance(id: "%s") {
                ticketsBreakdown {
                    totalCapacity
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
                    "totalTicketsSold": 2,
                    "totalTicketsCheckedIn": 1,
                    "totalTicketsToCheckIn": 1,
                    "totalTicketsAvailable": 48,
                }
            }
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize("with_perms", [True, False])
def test_tickets_breakdown(gql_client, with_perms):
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

    # Create booking

    booking = BookingFactory(performance=performance)
    [
        TicketFactory(
            booking=booking,
            seat_group=performance_seat_group_1.seat_group,
            concession_type=discount_requirement_1.concession_type,
        )
        for _ in range(10)
    ]

    if with_perms:
        gql_client.login().user.assign_perm("view_production", performance.production)

    response = gql_client.execute(
        """
        {
          performances {
            edges {
              node {
              	ticketOptions {
                  numberTicketsSold
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
                                    "numberTicketsSold": None if not with_perms else 10,
                                    "capacityRemaining": performance.seat_group_capacity_remaining(
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
                                    "numberTicketsSold": None if not with_perms else 0,
                                    "capacityRemaining": performance.seat_group_capacity_remaining(
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
@pytest.mark.parametrize(
    "logged_in,status",
    [(True, "DRAFT"), (True, "PENDING"), (False, "DRAFT"), (False, "PENDING")],
)
def test_productions_are_filtered_out(logged_in, status, gql_client):
    _ = [ProductionFactory() for _ in range(3)]
    draft_production = ProductionFactory(status=status, slug="my-show")

    request = """
        {
          productions {
            edges {
              node {
                id
              }
            }
          }
          production(slug: "my-show") {
              name
          }
        }
        """
    if logged_in:
        gql_client.login()
    response = gql_client.execute(request)

    assert len(response["data"]["productions"]["edges"]) == 3
    assert to_global_id("PerformanceNode", draft_production.id) not in [
        edge["node"]["id"] for edge in response["data"]["productions"]["edges"]
    ]
    assert response["data"]["production"] is None


@pytest.mark.django_db
def test_performances_are_shown_with_permission(gql_client):
    _ = [PerformanceFactory() for _ in range(3)]
    draft_performance = PerformanceFactory(
        production=ProductionFactory(status=Production.Status.DRAFT)
    )

    assign_perm(
        "productions.view_production",
        gql_client.login().user,
        draft_performance.production,
    )

    request = """
        {
          performances {
            edges {
              node {
                id
              }
            }
          }
          performance(id: "%s") {
              start
          }
        }
        """ % to_global_id(
        "PerformanceNode", draft_performance.id
    )
    response = gql_client.execute(request)

    assert len(response["data"]["performances"]["edges"]) == 4
    assert response["data"]["performance"] is not None


@pytest.mark.django_db
def test_performance_run_on(gql_client):
    query_datetime = timezone.datetime(
        year=2000, month=6, day=20, tzinfo=timezone.get_current_timezone()
    )
    _ = [
        PerformanceFactory(
            start=query_datetime + timezone.timedelta(days=i),
            end=query_datetime + timezone.timedelta(days=i, hours=2),
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
    response = gql_client.execute(request % query_datetime.date())
    assert response["data"]["performances"]["edges"] == [
        {"node": {"start": perm.start.isoformat()}}
        for perm in Performance.objects.running_on(query_datetime.date())
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


###
# Warnings Queries
###


@pytest.mark.django_db
def test_warnings(gql_client):
    ContentWarningFactory(short_description="Beware of the children")
    ContentWarningFactory(short_description="Pyrotechnics go bang")
    ContentWarningFactory(short_description="Strobe do be flickering")

    request = """
        query {
            warnings{
                edges {
                    node {
                        shortDescription
                    }
                }
            }
        }
    """

    response = gql_client.execute(request)
    assert response["data"]["warnings"]["edges"] == [
        {"node": {"shortDescription": "Beware of the children"}},
        {"node": {"shortDescription": "Pyrotechnics go bang"}},
        {"node": {"shortDescription": "Strobe do be flickering"}},
    ]
