import pytest
from django.contrib.auth.models import Permission
from django.utils import timezone
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.models import Booking
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
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_bookings_schema(gql_client_flexible, gql_id):

    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    # Create a booking that is not owned by the same user
    BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    tickets = [TicketFactory(booking=booking) for _ in range(10)]

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
                  status {
                    value
                    description
                  }
                  user {
                    id
                  }
                }
              }
            }
          }
        }
        """
    client = gql_client_flexible

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
                                "id": gql_id(booking.id, "BookingNode"),
                                "createdAt": booking.created_at.isoformat(),
                                "updatedAt": booking.updated_at.isoformat(),
                                "tickets": [
                                    {"id": gql_id(ticket.id, "TicketNode")}
                                    for ticket in tickets
                                ],
                                "reference": str(booking.reference),
                                "performance": {
                                    "id": gql_id(
                                        booking.performance.id, "PerformanceNode"
                                    )
                                },
                                "status": {
                                    "value": "IN_PROGRESS",
                                    "description": "In Progress",
                                },
                                "user": {"id": gql_id(booking.user.id, "UserNode")},
                            }
                        }
                    ]
                }
            }
        }
    }


@pytest.mark.django_db
def test_bookings_price_break_down(
    gql_client_flexible, gql_id
):  # pylint: disable=too-many-locals
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
    client = gql_client_flexible
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
                "id": gql_id(
                    ticket_group["seat_group"].id,
                    "SeatGroupNode",
                ),
            },
            "concessionType": {
                "id": gql_id(
                    ticket_group["concession_type"].id,
                    "ConcessionTypeNode",
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
        "subtotalPrice": booking.subtotal(),
        "miscCostsValue": int(booking.misc_costs_value()),
        "totalPrice": booking.total(),
        "ticketsDiscountedPrice": booking.total(),
    }


@pytest.mark.django_db
def test_discounts_node(gql_client, gql_id):
    performance = PerformanceFactory()

    # Create a discount
    discount = DiscountFactory(name="Family", percentage=0.2)
    discount.performances.set([performance])
    _ = [
        DiscountRequirementFactory(discount=discount, number=2),
        DiscountRequirementFactory(discount=discount, number=1),
    ]

    # Single discount - should not appear
    discount_2 = DiscountFactory(name="Student", percentage=0.3)
    discount_2.performances.set([performance])
    DiscountRequirementFactory(discount=discount_2, number=1)

    response = gql_client.execute(
        """
        {
          performances {
            edges {
              node {
                discounts {
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
        """
    )
    assert response == {
        "data": {
            "performances": {
                "edges": [
                    {
                        "node": {
                            "discounts": [
                                {
                                    "id": gql_id(discount.id, "DiscountNode"),
                                    "percentage": discount.percentage,
                                    "name": discount.name,
                                    "seatGroup": {
                                        gql_id(
                                            discount.seat_group.id,
                                            "SeatGroupNode",
                                        )
                                    }
                                    if discount.seat_group
                                    else None,
                                    "requirements": [
                                        {
                                            "id": gql_id(
                                                requirement.id,
                                                "DiscountRequirementNode",
                                            ),
                                            "number": requirement.number,
                                            "discount": {
                                                "id": gql_id(
                                                    requirement.discount.id,
                                                    "DiscountNode",
                                                )
                                            },
                                            "concessionType": {
                                                "id": gql_id(
                                                    requirement.concession_type.id,
                                                    "ConcessionTypeNode",
                                                )
                                            },
                                        }
                                        for requirement in discount.requirements.all()
                                    ],
                                }
                            ]
                        }
                    }
                ]
            }
        },
    }


@pytest.mark.django_db
def test_booking_in_progress(gql_client_flexible, gql_id):
    """
    We will often want to get an "in_progress" booking for a given booking and user.
        bookings(performance: "UGVyZm9ybWFuY2VOb2RlOjE=", status: "IN_PROGRESS")
    """
    user = UserFactory()
    performance = PerformanceFactory(id=1)
    # Create some completed bookings for the same performance
    _ = [
        BookingFactory(
            user=user, performance=performance, status=Booking.BookingStatus.PAID
        )
        for i in range(10)
    ]
    # Create some bookings for dfferent performances
    _ = [BookingFactory(user=user) for i in range(10)]
    booking = BookingFactory(
        user=user, performance=performance, status=Booking.BookingStatus.IN_PROGRESS
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

    gql_client_flexible.user = user
    response = gql_client_flexible.execute(request_query)

    assert response == {
        "data": {
            "me": {
                "bookings": {
                    "edges": [
                        {
                            "node": {
                                "id": gql_id(booking.id, "BookingNode"),
                            }
                        },
                    ]
                }
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "order_by, expected_order",
    [
        ("createdAt", [0, 1, 2]),
        ("-createdAt", [2, 1, 0]),
    ],
)
def test_booking_orderby(order_by, expected_order, gql_client_flexible):
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
    gql_client_flexible.user = user
    response = gql_client_flexible.execute(request % order_by)

    assert response["data"]["me"]["bookings"]["edges"] == [
        {"node": {"createdAt": bookings[i].created_at.isoformat()}}
        for i in expected_order
    ]


@pytest.mark.django_db
def test_bookings_auth(gql_client_flexible):
    user = gql_client_flexible.request_factory.user
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
    response = gql_client_flexible.execute(request_query)
    assert (
        len(response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"])
        == 1
    )

    # When we are logged out expect 0 booking
    gql_client_flexible.logout()
    response = gql_client_flexible.execute(request_query)
    assert (
        response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"] == []
    )

    # When we are logged in as a different user expect 0 booking
    user2 = UserFactory()
    gql_client_flexible.user = user2
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
def test_bookings_search(
    search_phrase, expected_filtered_bookings, gql_client_flexible
):
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
    gql_client_flexible.user.user_permissions.add(boxoffice_perm)

    response = gql_client_flexible.execute(request)
    assert [node["node"]["id"] for node in response["data"]["bookings"]["edges"]] == [
        to_global_id("BookingNode", booking_id)
        for booking_id in expected_filtered_bookings
    ]


@pytest.mark.django_db
def test_bookings_qs(gql_client_flexible):
    """
    The bookings query should only return bookings that the user has permission to view.
    """

    # Booking owned by user
    BookingFactory(id=1, user=gql_client_flexible.user)

    # Booking user does not have permission to acess
    BookingFactory(id=2)

    # Booking that user has permission to boxoffice
    booking = BookingFactory(id=3)
    assign_perm("boxoffice", gql_client_flexible.user, booking.performance.production)

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

    response = gql_client_flexible.execute(request)
    assert [node["node"]["id"] for node in response["data"]["bookings"]["edges"]] == [
        to_global_id("BookingNode", booking_id) for booking_id in [1, 3]
    ]

    # If the user is a superuser they should be able to access all bookngs
    gql_client_flexible.user.is_superuser = True
    gql_client_flexible.user.save()

    response = gql_client_flexible.execute(request)
    assert [node["node"]["id"] for node in response["data"]["bookings"]["edges"]] == [
        to_global_id("BookingNode", booking_id) for booking_id in [1, 2, 3]
    ]

@pytest.mark.django_db
def test_booking_filters():

        # No tickets booking
    booking_no_tickets = BookingFactory()

    # None checked in
    booking_none = BookingFactory()
    TicketFactory(booking=booking_none)
    TicketFactory(booking=booking_none)

    # Some checked in
    booking_some = BookingFactory()
    TicketFactory(booking=booking_some, checked_in=True)
    TicketFactory(booking=booking_some)

    # All checked in
    booking_all = BookingFactory()
    TicketFactory(booking=booking_all, checked_in=True)
    TicketFactory(booking=booking_all, checked_in=True)

    
    request = """
        {
          bookings(checked_in) {
            edges {
              node {
                id
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
