# pylint: disable=too-many-lines
import datetime

import pytest
from django.contrib.auth.models import AnonymousUser, Permission
from django.utils import timezone
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.models import Ticket
from uobtheatre.bookings.schema import TicketNode
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PercentageMiscCostFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
)
from uobtheatre.payments.payables import Payable
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_tickets_schema(gql_client):
    gql_client.login().user
    booking = BookingFactory()
    tickets = [TicketFactory(booking=booking) for _ in range(1)]
    for ticket in tickets:
        ticket.check_in(user=UserFactory())

    request_query = """
        {
          performances {
            edges {
              node {
                bookings {
                  edges {
                    node {
                      tickets {
                        id
                        checkedIn
                        checkedInAt
                        checkedInBy {
                          id
                        }
                        seatGroup {
                          id
                        }
                        booking {
                          id
                        }
                        concessionType {
                          id
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

    assign_perm(
        "productions.boxoffice", gql_client.user, booking.performance.production
    )

    response = gql_client.execute(request_query)
    assert response == {
        "data": {
            "performances": {
                "edges": [
                    {
                        "node": {
                            "bookings": {
                                "edges": [
                                    {
                                        "node": {
                                            "tickets": [
                                                {
                                                    "id": to_global_id(
                                                        "TicketNode", ticket.id
                                                    ),
                                                    "checkedIn": ticket.checked_in,
                                                    "checkedInAt": ticket.checked_in_at.isoformat(),
                                                    "checkedInBy": {
                                                        "id": to_global_id(
                                                            "UserNode",
                                                            ticket.checked_in_by.id,
                                                        )
                                                    },
                                                    "seatGroup": {
                                                        "id": to_global_id(
                                                            "SeatGroupNode",
                                                            ticket.seat_group.id,
                                                        )
                                                    },
                                                    "booking": {
                                                        "id": to_global_id(
                                                            "BookingNode",
                                                            ticket.booking.id,
                                                        )
                                                    },
                                                    "concessionType": {
                                                        "id": to_global_id(
                                                            "ConcessionTypeNode",
                                                            ticket.concession_type.id,
                                                        )
                                                    },
                                                }
                                                for ticket in tickets
                                            ],
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        }
    }

    # When there is no user expect no bookings
    gql_client.logout()
    response = gql_client.execute(request_query)
    assert (
        response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"] == []
    )


@pytest.mark.django_db
def test_ticket_checked_in_by_perm(gql_client):
    user = gql_client.login().user
    booking = BookingFactory(user=user)
    tickets = [TicketFactory(booking=booking) for _ in range(1)]

    check_in_user = UserFactory()
    for ticket in tickets:
        ticket.check_in(user=check_in_user)

    request = """
      {
        performances {
          edges {
            node {
              bookings {
                edges {
                  node {
                    tickets {
                      checkedInBy {
                        id
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
      """
    response = gql_client.execute(request)
    assert (
        response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"][0][
            "node"
        ]["tickets"][0]["checkedInBy"]
        is None
    )

    assign_perm("productions.boxoffice", user, booking.performance.production)

    response = gql_client.execute(request)
    assert response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"][0][
        "node"
    ]["tickets"][0]["checkedInBy"] == {"id": to_global_id("UserNode", check_in_user.id)}


@pytest.mark.django_db
def test_bookings_schema(gql_client):
    booking = BookingFactory(status=Payable.Status.IN_PROGRESS)
    # Create a booking that is not owned by the same user
    BookingFactory(status=Payable.Status.IN_PROGRESS)
    tickets = [TicketFactory(booking=booking) for _ in range(1)]

    request_query = """
        {
          me {
            bookings {
              edges {
                node {
                  id
                  createdAt
                  updatedAt
                  tickets {
                    id
                  }
                  reference
                  performance {
                    id
                  }
                  status
                  user {
                    id
                  }
                  salesBreakdown {
                    totalPayments
                    totalRefunds
                    netTransactions
                  }
                }
              }
            }
          }
        }
        """
    client = gql_client

    # When there is no user expect no bookings
    client.logout()
    response = client.execute(request_query)
    assert response == {"data": {"me": None}}

    # When we are logged in expect only the user's bookings
    client.user = booking.user
    response = client.execute(request_query)
    assert response == {
        "data": {
            "me": {
                "bookings": {
                    "edges": [
                        {
                            "node": {
                                "id": to_global_id("BookingNode", booking.id),
                                "createdAt": booking.created_at.isoformat(),
                                "updatedAt": booking.updated_at.isoformat(),
                                "tickets": [
                                    {"id": to_global_id("TicketNode", ticket.id)}
                                    for ticket in tickets
                                ],
                                "reference": str(booking.reference),
                                "performance": {
                                    "id": to_global_id(
                                        "PerformanceNode", booking.performance.id
                                    )
                                },
                                "status": "IN_PROGRESS",
                                "user": {
                                    "id": to_global_id("UserNode", booking.user.id)
                                },
                                "salesBreakdown": {
                                    "totalPayments": booking.sales_breakdown.total_payments,
                                    "totalRefunds": booking.sales_breakdown.total_refunds,
                                    "netTransactions": booking.sales_breakdown.net_transactions,
                                },
                            }
                        }
                    ]
                }
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "expired",
    [False, True],
)
def test_booking_expires_at(gql_client, expired):
    gql_client.login()
    booking = BookingFactory(status=Payable.Status.IN_PROGRESS, user=gql_client.user)
    if expired:
        booking.expires_at = timezone.now() - datetime.timedelta(minutes=30)
        booking.save()

    request_query = """
        {
            me {
              bookings(id: "%s") {
                  edges {
                    node {
                      expiresAt
                      expired
                    }
                  }
              }
            }
        }
        """

    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )

    assert (
        response["data"]["me"]["bookings"]["edges"][0]["node"]["expiresAt"] is not None
    )
    assert response["data"]["me"]["bookings"]["edges"][0]["node"]["expired"] is expired


@pytest.mark.django_db
def test_bookings_price_break_down(gql_client):  # pylint: disable=too-many-locals
    booking = BookingFactory()

    # Create 3 tickets with the same seat group and concession type
    seat_group_1 = SeatGroupFactory()
    psg_1 = PerformanceSeatingFactory(
        performance=booking.performance, seat_group=seat_group_1
    )
    concession_type_1 = ConcessionTypeFactory()
    _ = [
        TicketFactory(
            seat_group=seat_group_1, concession_type=concession_type_1, booking=booking
        )
        for _ in range(3)
    ]

    # Create 2 with the same seat group but a different concession type
    concession_type_2 = ConcessionTypeFactory()
    _ = [
        TicketFactory(
            seat_group=seat_group_1, concession_type=concession_type_2, booking=booking
        )
        for _ in range(2)
    ]

    # Create 2 with the same concession but a different seat groups
    seat_group_2 = SeatGroupFactory()
    psg_2 = PerformanceSeatingFactory(
        performance=booking.performance, seat_group=seat_group_2
    )
    _ = [
        TicketFactory(
            seat_group=seat_group_2, concession_type=concession_type_1, booking=booking
        )
        for _ in range(2)
    ]

    expected_ticket_groups = [
        {
            "seat_group": seat_group_1,
            "concession_type": concession_type_1,
            "number": 3,
            "price": psg_1.price,
        },
        {
            "seat_group": seat_group_1,
            "concession_type": concession_type_2,
            "number": 2,
            "price": psg_1.price,
        },
        {
            "seat_group": seat_group_2,
            "concession_type": concession_type_1,
            "number": 2,
            "price": psg_2.price,
        },
    ]

    # Add in some misc costs
    value_misc_costs = [ValueMiscCostFactory() for _ in range(2)]
    percentage_misc_cost = [PercentageMiscCostFactory() for _ in range(2)]

    def misc_cost_to_dict(misc_cost):
        return {
            "value": misc_cost.get_value(booking),
            "percentage": misc_cost.percentage,
            "description": misc_cost.description,
            "name": misc_cost.name,
        }

    misc_cost_expected = list(
        map(misc_cost_to_dict, value_misc_costs + percentage_misc_cost)
    )

    request_query = """
        {
          me {
            bookings {
              edges {
                node {
                  priceBreakdown {
                    ticketsPrice
                    discountsValue
                    subtotalPrice
                    miscCostsValue
                    totalPrice
                    tickets {
                      ticketPrice
                      number
                      totalPrice
                      seatGroup {
                        id
                      }
                      concessionType {
                        id
                      }
                    }
                    ticketsDiscountedPrice
                    miscCosts {
                      value
                      percentage
                      description
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """
    # Login in client
    client = gql_client
    client.user = booking.user
    response = client.execute(request_query)

    response_booking_price_break_down = response["data"]["me"]["bookings"]["edges"][0][
        "node"
    ]["priceBreakdown"]
    assert response_booking_price_break_down.pop("tickets") == [
        {
            "ticketPrice": ticket_group["price"],
            "number": ticket_group["number"],
            "seatGroup": {
                "id": to_global_id(
                    "SeatGroupNode",
                    ticket_group["seat_group"].id,
                ),
            },
            "concessionType": {
                "id": to_global_id(
                    "ConcessionTypeNode",
                    ticket_group["concession_type"].id,
                ),
            },
            "totalPrice": ticket_group["number"] * ticket_group["price"],
        }
        for ticket_group in expected_ticket_groups
    ]

    assert response_booking_price_break_down.pop("miscCosts") == misc_cost_expected

    assert response_booking_price_break_down == {
        "ticketsPrice": booking.tickets_price(),
        "discountsValue": booking.discount_value(),
        "subtotalPrice": booking.subtotal,
        "miscCostsValue": int(booking.misc_costs_value),
        "totalPrice": booking.total,
        "ticketsDiscountedPrice": booking.subtotal,
    }


@pytest.mark.django_db
def test_discounts_node(gql_client):
    performance = PerformanceFactory()

    # Create a discount
    discount = DiscountFactory(name="Family", percentage=0.2)
    discount.performances.set([performance])
    _ = [
        DiscountRequirementFactory(discount=discount, number=2),
        DiscountRequirementFactory(discount=discount, number=1),
    ]

    response = gql_client.execute(
        """
        {
          performances {
            edges {
              node {
                discounts {
                  edges {
                    node {
                      id
                      percentage
                      name
                      seatGroup {
                        id
                      }
                      requirements {
                        id
                        number
                        discount {
                          id
                        }
                        concessionType {
                          id
                        }
                      }
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
                            "discounts": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": to_global_id(
                                                "DiscountNode", discount.id
                                            ),
                                            "percentage": discount.percentage,
                                            "name": discount.name,
                                            "seatGroup": (
                                                {
                                                    to_global_id(
                                                        "SeatGroupNode",
                                                        discount.seat_group.id,
                                                    )
                                                }
                                                if discount.seat_group
                                                else None
                                            ),
                                            "requirements": [
                                                {
                                                    "id": to_global_id(
                                                        "DiscountRequirementNode",
                                                        requirement.id,
                                                    ),
                                                    "number": requirement.number,
                                                    "discount": {
                                                        "id": to_global_id(
                                                            "DiscountNode",
                                                            requirement.discount.id,
                                                        )
                                                    },
                                                    "concessionType": {
                                                        "id": to_global_id(
                                                            "ConcessionTypeNode",
                                                            requirement.concession_type.id,
                                                        )
                                                    },
                                                }
                                                for requirement in discount.requirements.all()
                                            ],
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        },
    }


@pytest.mark.django_db
def test_booking_in_progress(gql_client):
    """
    We will often want to get an "in_progress" booking for a given booking and user.
        bookings(performance: "UGVyZm9ybWFuY2VOb2RlOjE=", status: "IN_PROGRESS")
    """
    user = UserFactory()
    performance = PerformanceFactory(id=1)
    # Create some completed bookings for the same performance
    _ = [
        BookingFactory(user=user, performance=performance, status=Payable.Status.PAID)
        for i in range(10)
    ]
    # Create some bookings for dfferent performances
    _ = [BookingFactory(user=user) for i in range(10)]
    booking = BookingFactory(
        user=user, performance=performance, status=Payable.Status.IN_PROGRESS
    )

    request_query = """
    {
      me {
        bookings(performance: "UGVyZm9ybWFuY2VOb2RlOjE=", status: "IN_PROGRESS") {
          edges {
            node {
              id
            }
          }
        }
      }
    }
    """

    gql_client.user = user
    response = gql_client.execute(request_query)

    assert response == {
        "data": {
            "me": {
                "bookings": {
                    "edges": [
                        {
                            "node": {
                                "id": to_global_id("BookingNode", booking.id),
                            }
                        },
                    ]
                }
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize("expired", [False, True])
def test_booking_expired(gql_client, expired):
    gql_client.login()

    expired_booking = BookingFactory(
        user=gql_client.user,
        status=Payable.Status.IN_PROGRESS,
        expires_at=timezone.now() - datetime.timedelta(minutes=20),
    )
    not_expired_booking = BookingFactory(
        user=gql_client.user, status=Payable.Status.IN_PROGRESS
    )

    request = (
        """
      {
        me {
          bookings(expired: %s) {
            edges {
              node {
                id
              }
            }
          }
        }
      }
    """
        % str(expired).lower()
    )

    response = gql_client.execute(request)
    assert len(response["data"]["me"]["bookings"]["edges"]) == 1
    assert response["data"]["me"]["bookings"]["edges"][0]["node"]["id"] == to_global_id(
        "BookingNode", expired_booking.id if expired else not_expired_booking.id
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "order_by, expected_order",
    [
        ("createdAt", [0, 1, 2]),
        ("-createdAt", [2, 1, 0]),
    ],
)
def test_booking_orderby(order_by, expected_order, gql_client):
    """
    Test for the ordfering of a user's bookings
    """
    timezone.now()
    user = UserFactory()
    bookings = []

    # Create bookings in order, this first booking in the list is the first to be created
    for _ in range(3):
        bookings.append(BookingFactory(user=user))

    request = """
    {
      me {
        bookings(orderBy: "%s") {
          edges {
            node {
              createdAt
            }
          }
        }
      }
    }
    """
    gql_client.user = user
    response = gql_client.execute(request % order_by)

    assert response["data"]["me"]["bookings"]["edges"] == [
        {"node": {"createdAt": bookings[i].created_at.isoformat()}}
        for i in expected_order
    ]


@pytest.mark.django_db
def test_bookings_auth(gql_client):
    user = gql_client.login().user
    BookingFactory(user=user)

    request_query = """
    {
      performances {
        edges {
          node {
            bookings {
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

    # When we are logged in expect 1 booking
    response = gql_client.execute(request_query)
    assert (
        len(response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"])
        == 1
    )

    # When we are logged out expect 0 booking
    gql_client.logout()
    response = gql_client.execute(request_query)
    assert (
        response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"] == []
    )

    # When we are logged in as a different user expect 0 booking
    user2 = UserFactory()
    gql_client.user = user2
    assert (
        response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"] == []
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "search_phrase, expected_filtered_bookings",
    [
        ("jam", [1]),
        ("alex", [2]),
        ("abc", [1, 2]),
        ("def", [2]),
        ("mrfantastic", [2]),
        ("irrelvent words mrfantastic", [2]),
        ("james alex", [1, 2]),
    ],
)
def test_bookings_search(search_phrase, expected_filtered_bookings, gql_client):
    user_1 = UserFactory(
        first_name="James", last_name="Elgar", email="jameselgar@email.com"
    )
    user_2 = UserFactory(
        first_name="Alex", last_name="Toff", email="mrfantastic@email.com"
    )
    BookingFactory(id=1, user=user_1, reference="abc123")
    BookingFactory(id=2, user=user_2, reference="abcdef")

    request = (
        """
        query {
            bookings(search:"%s") {
        	  edges {
        	    node {
        	      id
        	    }
        	  }
        	}
        }
    """
        % search_phrase
    )

    boxoffice_perm = Permission.objects.get(codename="boxoffice")
    gql_client.login().user.user_permissions.add(boxoffice_perm)

    response = gql_client.execute(request)

    response_bookings_id = [
        node["node"]["id"] for node in response["data"]["bookings"]["edges"]
    ]
    expected_booking_ids = [
        to_global_id("BookingNode", booking_id)
        for booking_id in expected_filtered_bookings
    ]

    assert len(response_bookings_id) == len(expected_booking_ids)
    assert set(response_bookings_id) == set(expected_booking_ids)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "slug, expected_filtered_bookings",
    [
        ("", [1, 2, 3, 4, 5]),  # Empty should return all
        ("test", [1, 2]),  # Check multiple performances for a production
        ("teeth", [3, 4]),  # Check multiple bookings for a performances
        ("te", []),  # Check matches whole slug
        ("test teeth", []),  # Check spaces aren't treated as an OR
        ("teeth-test", [5]),  # Check hyphens work correctly
    ],
)
def test_bookings_slug_filter(slug, expected_filtered_bookings, gql_client):

    production_1 = ProductionFactory(name="Test")
    production_2 = ProductionFactory(name="Teeth")
    production_3 = ProductionFactory(name="Teeth Test")

    performance_1 = PerformanceFactory(production=production_1)
    performance_2 = PerformanceFactory(production=production_1)
    performance_3 = PerformanceFactory(production=production_2)
    performance_4 = PerformanceFactory(production=production_3)

    BookingFactory(id=1, performance=performance_1)  # slug: test
    BookingFactory(id=2, performance=performance_2)  # slug: test
    BookingFactory(id=3, performance=performance_3)  # slug: teeth
    BookingFactory(id=4, performance=performance_3)  # slug: teeth
    BookingFactory(id=5, performance=performance_4)  # slug: teeth-test

    request = (
        """
            query {
                bookings(productionSlug:"%s") {
                  edges {
                    node {
                      id
                    }
                  }
                }
            }
        """
        % slug
    )

    boxoffice_perm = Permission.objects.get(codename="boxoffice")
    gql_client.login().user.user_permissions.add(boxoffice_perm)

    response = gql_client.execute(request)

    response_bookings_id = [
        node["node"]["id"] for node in response["data"]["bookings"]["edges"]
    ]
    expected_booking_ids = [
        to_global_id("BookingNode", booking_id)
        for booking_id in expected_filtered_bookings
    ]

    assert len(response_bookings_id) == len(expected_booking_ids)
    assert set(response_bookings_id) == set(expected_booking_ids)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "performance_id, expected_filtered_bookings",
    [
        ("", [1, 2, 3]),  # Empty should return all, but not error
        (to_global_id("PerformanceNode", 10), [1]),  # Check basic query
        # Check multiple bookings for a performance
        (to_global_id("PerformanceNode", 20), [2, 3]),
        # Check performances that don't exist - should not error
        (to_global_id("PerformanceNode", 30), []),
    ],
)
def test_bookings_performance_id(
    performance_id, expected_filtered_bookings, gql_client
):

    performance_1 = PerformanceFactory(id=10)
    performance_2 = PerformanceFactory(id=20)

    BookingFactory(id=1, performance=performance_1)  # id: 10
    BookingFactory(id=2, performance=performance_2)  # id: 20
    BookingFactory(id=3, performance=performance_2)  # id: 20

    request = (
        """
            query {
                bookings(performanceId:"%s") {
                  edges {
                    node {
                      id
                    }
                  }
                }
            }
        """
        % performance_id
    )

    boxoffice_perm = Permission.objects.get(codename="boxoffice")
    gql_client.login().user.user_permissions.add(boxoffice_perm)

    response = gql_client.execute(request)

    response_bookings_id = [
        node["node"]["id"] for node in response["data"]["bookings"]["edges"]
    ]
    expected_booking_ids = [
        to_global_id("BookingNode", booking_id)
        for booking_id in expected_filtered_bookings
    ]

    assert len(response_bookings_id) == len(expected_booking_ids)
    assert set(response_bookings_id) == set(expected_booking_ids)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "search_phrase, expected_filtered_bookings",
    [
        ("prod", [1, 2, 3]),  # Check case-insensitivity
        ("prod ", [1, 2, 3]),  # Check *final* spaces *are* stripped
        ("prod2", [3]),  # Check spaces within prod name *aren't* ignored
        ("prod 2", [2]),  # Check spaces *aren't* treated as an OR, and also
        # check *internal* spaces *aren't* stripped
        ("def", []),  # Check actually filtering
        ("", [1, 2, 3]),  # Empty string should return all
        ("aces", [2, 3]),  # Check matches all the way to the end; doesn't need
        # full word
    ],
)
def test_bookings_productions_search(
    search_phrase, expected_filtered_bookings, gql_client
):

    prod1 = ProductionFactory(name="Prod1")
    prod2 = ProductionFactory(name="prod 2 spaces")
    prod3 = ProductionFactory(name="prod2spaces")

    BookingFactory(id=1, performance=PerformanceFactory(production=prod1))
    BookingFactory(id=2, performance=PerformanceFactory(production=prod2))
    BookingFactory(id=3, performance=PerformanceFactory(production=prod3))

    request = (
        """
            query {
                bookings(productionSearch:"%s") {
                  edges {
                    node {
                      id
                    }
                  }
                }
            }
        """
        % search_phrase
    )

    boxoffice_perm = Permission.objects.get(codename="boxoffice")
    gql_client.login().user.user_permissions.add(boxoffice_perm)

    response = gql_client.execute(request)

    response_bookings_id = [
        node["node"]["id"] for node in response["data"]["bookings"]["edges"]
    ]
    expected_booking_ids = [
        to_global_id("BookingNode", booking_id)
        for booking_id in expected_filtered_bookings
    ]

    assert len(response_bookings_id) == len(expected_booking_ids)
    assert set(response_bookings_id) == set(expected_booking_ids)


@pytest.mark.django_db
def test_bookings_qs(gql_client):
    """
    The bookings query should only return bookings that the user has permission to view.
    """

    # Booking owned by user
    BookingFactory(id=1, user=gql_client.login().user)

    # Booking user does not have permission to acess
    BookingFactory(id=2)

    # Booking that user has permission to boxoffice
    booking = BookingFactory(id=3)
    assign_perm("boxoffice", gql_client.user, booking.performance.production)

    request = """
        query {
            bookings {
        	  edges {
        	    node {
        	      id
        	    }
        	  }
        	}
        }
    """

    response = gql_client.execute(request)
    assert {node["node"]["id"] for node in response["data"]["bookings"]["edges"]} == {
        to_global_id("BookingNode", booking_id) for booking_id in [1, 3]
    }

    # If the user is a superuser they should be able to access all bookngs
    gql_client.user.is_superuser = True
    gql_client.user.save()

    response = gql_client.execute(request)
    assert {node["node"]["id"] for node in response["data"]["bookings"]["edges"]} == {
        to_global_id("BookingNode", booking_id) for booking_id in [1, 2, 3]
    }


@pytest.mark.django_db
def test_booking_filter_checked_in(gql_client):
    # No tickets booking
    _ = BookingFactory(user=gql_client.login().user)

    # None checked in
    booking_none = BookingFactory(user=gql_client.user)
    TicketFactory(booking=booking_none)
    TicketFactory(booking=booking_none)

    # Some checked in
    booking_some = BookingFactory(user=gql_client.user)
    TicketFactory(booking=booking_some, set_checked_in=True)
    TicketFactory(booking=booking_some)

    # All checked in
    booking_all = BookingFactory(user=gql_client.user)
    TicketFactory(booking=booking_all, set_checked_in=True)
    TicketFactory(booking=booking_all, set_checked_in=True)

    true_expected_set = {booking_all.reference}
    false_expected_set = {booking_none.reference, booking_some.reference}

    request = """
        {
          bookings(checkedIn: %s) {
            edges {
              node {
                reference
              }
            }
          }
        }
        """

    # Ask for nothing and check you get nothing
    true_response = gql_client.execute(request % "true")
    false_response = gql_client.execute(request % "false")

    true_response_set = set()
    false_response_set = set()

    true_response_set = {
        booking["node"]["reference"]
        for booking in true_response["data"]["bookings"]["edges"]
    }
    false_response_set = {
        booking["node"]["reference"]
        for booking in false_response["data"]["bookings"]["edges"]
    }

    assert true_response_set == true_expected_set
    assert false_response_set == false_expected_set


@pytest.mark.django_db
def test_booking_filter_active(gql_client):
    now = timezone.now()

    production = ProductionFactory()

    performance_future = PerformanceFactory(
        production=production, end=now + datetime.timedelta(days=2)
    )
    performance_past = PerformanceFactory(
        production=production, end=now + datetime.timedelta(days=-2)
    )

    booking_future = BookingFactory(
        user=gql_client.login().user, performance=performance_future
    )
    booking_past = BookingFactory(user=gql_client.user, performance=performance_past)

    true_expected_set = {booking_future.reference}
    false_expected_set = {booking_past.reference}

    request = """
        {
          bookings(active: %s) {
            edges {
              node {
                reference
              }
            }
          }
        }
        """

    true_response = gql_client.execute(request % "true")
    false_response = gql_client.execute(request % "false")

    true_response_set = {
        booking["node"]["reference"]
        for booking in true_response["data"]["bookings"]["edges"]
    }
    false_response_set = {
        booking["node"]["reference"]
        for booking in false_response["data"]["bookings"]["edges"]
    }

    assert true_response_set == true_expected_set
    assert false_response_set == false_expected_set


@pytest.mark.django_db
def test_booking_order_checked_in(gql_client):
    # None checked in
    booking_none = BookingFactory(user=gql_client.login().user)
    TicketFactory(booking=booking_none)
    TicketFactory(booking=booking_none)

    # Some checked in
    booking_some = BookingFactory(user=gql_client.user)
    TicketFactory(booking=booking_some, set_checked_in=True)
    TicketFactory(booking=booking_some)

    # All checked in
    booking_all = BookingFactory(user=gql_client.user)
    TicketFactory(booking=booking_all, set_checked_in=True)
    TicketFactory(booking=booking_all, set_checked_in=True)

    desc_expected_list = [
        booking_all.reference,
        booking_some.reference,
        booking_none.reference,
    ]
    asec_expected_list = [
        booking_none.reference,
        booking_some.reference,
        booking_all.reference,
    ]

    request = """
        {
          bookings(orderBy: "%s") {
            edges {
              node {
                reference
              }
            }
          }
        }
        """

    # Ask for nothing and check you get nothing
    desc_response = gql_client.execute(request % "checkedIn")
    asec_response = gql_client.execute(request % "-checkedIn")

    desc_response_list = [
        booking["node"]["reference"]
        for booking in desc_response["data"]["bookings"]["edges"]
    ]
    asec_response_list = [
        booking["node"]["reference"]
        for booking in asec_response["data"]["bookings"]["edges"]
    ]

    assert desc_response_list == desc_expected_list
    assert asec_response_list == asec_expected_list


@pytest.mark.django_db
def test_booking_order_start(gql_client):
    now = timezone.now()

    # First
    performance_soonest = PerformanceFactory(start=now + datetime.timedelta(days=2))
    booking_soonest = BookingFactory(
        user=gql_client.login().user, performance=performance_soonest
    )

    # Second
    performance_middle = PerformanceFactory(start=now + datetime.timedelta(days=6))
    booking_middle = BookingFactory(
        user=gql_client.user, performance=performance_middle
    )

    # Last
    performance_last = PerformanceFactory(start=now + datetime.timedelta(days=24))
    booking_last = BookingFactory(user=gql_client.user, performance=performance_last)

    desc_expected_list = [
        booking_soonest.reference,
        booking_middle.reference,
        booking_last.reference,
    ]
    asec_expected_list = [
        booking_last.reference,
        booking_middle.reference,
        booking_soonest.reference,
    ]

    request = """
        {
          bookings(orderBy: "%s") {
            edges {
              node {
                reference
              }
            }
          }
        }
        """

    # Ask for nothing and check you get nothing
    desc_response = gql_client.execute(request % "start")
    asec_response = gql_client.execute(request % "-start")

    desc_response_list = [
        booking["node"]["reference"]
        for booking in desc_response["data"]["bookings"]["edges"]
    ]
    asec_response_list = [
        booking["node"]["reference"]
        for booking in asec_response["data"]["bookings"]["edges"]
    ]

    assert desc_response_list == desc_expected_list
    assert asec_response_list == asec_expected_list


@pytest.mark.django_db
@pytest.mark.parametrize(
    "logged_in, expected_includes",
    [
        (False, False),
        (True, True),
    ],
)
def test_ticket_node_queryset_with_anonymous_user(info, logged_in, expected_includes):
    ticket = TicketFactory(
        booking=BookingFactory(user=info.context.user)
    )  # Belongs to user
    TicketFactory()  # Doesn't belong to user

    if not logged_in:
        info.context.user = AnonymousUser()

    qs = TicketNode.get_queryset(Ticket.objects, info)
    assert list(qs.all()) == ([ticket] if expected_includes else [])
