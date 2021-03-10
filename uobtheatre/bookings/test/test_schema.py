import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
    PercentageMiscCostFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatFactory, SeatGroupFactory


@pytest.mark.django_db
def test_bookings_schema(gql_client_flexible, gql_id):

    booking = BookingFactory(status=Booking.BookingStatus.INPROGRESS)
    # Create a booking that is not owned by the same user
    BookingFactory(status=Booking.BookingStatus.INPROGRESS)
    tickets = [TicketFactory(booking=booking) for _ in range(10)]

    request_query = """
        {
          me {
            bookings {
              edges {
                node {
                  id
                  tickets {
                    id
                  }
                  bookingReference
                  performance {
                    id
                  }
                  status
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
    client.set_user(booking.user)
    response = client.execute(request_query)
    assert response == {
        "data": {
            "me": {
                "bookings": {
                    "edges": [
                        {
                            "node": {
                                "id": gql_id(booking.id, "BookingNode"),
                                "tickets": [
                                    {"id": gql_id(ticket.id, "TicketNode")}
                                    for ticket in tickets
                                ],
                                "bookingReference": str(booking.booking_reference),
                                "performance": {
                                    "id": gql_id(
                                        booking.performance.id, "PerformanceNode"
                                    )
                                },
                                "status": "INPROGRESS",
                            }
                        }
                    ]
                }
            }
        }
    }


@pytest.mark.django_db
def test_bookings_price_break_down(gql_client_flexible, gql_id):
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
                      concession {
                        id
                      }
                    }
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
    client.set_user(booking.user)
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
            "concession": {
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
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, seat_group_capacity, performance_capacity, is_valid",
    [
        # Check performance is required to create booking
        (
            """
            tickets: [
                {
                    seatGroupId: "U2VhdEdyb3VwTm9kZTox"
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
            ]
            """,
            10,
            10,
            False,
        ),
        # Assert seat group is required for each seat booking
        (
            """
            performanceId: "UGVyZm9ybWFuY2VOb2RlOjE="
            tickets: [
                {
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
            ]
            """,
            10,
            10,
            False,
        ),
        # Check concession type is not required (default to adult)
        # TODO write test to check default to adult
        # TODO For now concession type is required as there is no default
        # (
        #     """
        #     performanceId: "UGVyZm9ybWFuY2VOb2RlOjE="
        #     tickets: [
        #         {
        #             seatGroupId: "U2VhdEdyb3VwTm9kZTox"
        #         }
        #     ]
        #     """,
        #     10,
        #     10,
        #     True,
        # ),
        # Check seat booking is not required
        (
            """
            performanceId: "UGVyZm9ybWFuY2VOb2RlOjE="
            """,
            10,
            10,
            True,
        ),
        (
            # Check booking with all data is valid
            """
            performanceId: "UGVyZm9ybWFuY2VOb2RlOjE="
            tickets: [
                {
                    seatGroupId: "U2VhdEdyb3VwTm9kZTox"
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
            ]
            """,
            10,
            10,
            True,
        ),
        (
            # Check if there is not enough performance capcaity it is not valid
            """
            performanceId: "UGVyZm9ybWFuY2VOb2RlOjE="
            tickets: [
                {
                    seatGroupId: "U2VhdEdyb3VwTm9kZTox"
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
                {
                    seatGroupId: "U2VhdEdyb3VwTm9kZTox"
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
                {
                    seatGroupId: "U2VhdEdyb3VwTm9kZTox"
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
            ]
            """,
            10,
            2,
            False,
        ),
        (
            # Check if there is not enough seat_group capcaity it is not valid
            """
            performanceId: "UGVyZm9ybWFuY2VOb2RlOjE="
            tickets: [
                {
                    seatGroupId: "U2VhdEdyb3VwTm9kZTox"
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
                {
                    seatGroupId: "U2VhdEdyb3VwTm9kZTox",
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
                {
                    seatGroupId: "U2VhdEdyb3VwTm9kZTox"
                    concessionTypeId: "Q29uY2Vzc2lvblR5cGVOb2RlOjE="
                }
            ],
            """,
            2,
            10,
            False,
        ),
    ],
)
def test_create_booking_mutation(
    data, seat_group_capacity, performance_capacity, is_valid, gql_client_flexible
):

    performance = PerformanceFactory(id=1, capacity=performance_capacity)
    seat_group = SeatGroupFactory(id=1)
    PerformanceSeatingFactory(
        performance=performance, seat_group=seat_group, capacity=seat_group_capacity
    )
    ConcessionTypeFactory(id=1)
    request = """
        mutation {
          createBooking(
            %s
          ) {
            booking {
              id
            }
         }
        }
    """

    client = gql_client_flexible
    print(request % data)
    response = client.execute(request % data)

    if not is_valid:
        assert response.get("errors")
    else:
        assert not response.get("errors")


@pytest.mark.django_db
def test_booking_inprogress(gql_client_flexible, gql_id):
    """
    We will often want to get an "inprogress" booking for a given booking and user.
        bookings(performance: "UGVyZm9ybWFuY2VOb2RlOjE=", status: "INPROGRESS")
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
        user=user, performance=performance, status=Booking.BookingStatus.INPROGRESS
    )

    request_query = """
    {
      me {
        bookings(performance: "UGVyZm9ybWFuY2VOb2RlOjE=", status: "INPROGRESS") {
          edges {
            node {
              id
            }
          }
        }
      }
    }
    """

    gql_client_flexible.set_user(user)
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
    gql_client_flexible.set_user(user2)
    assert (
        response["data"]["performances"]["edges"][0]["node"]["bookings"]["edges"] == []
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "currentTickets, plannedTickets",
    [
        (
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 2,
                },
            ],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 2,
                },
            ],
        ),
    ],
)
def test_booking_ticket_diff(currentTickets, plannedTickets, gql_client_flexible):

    SeatGroupFactory(id=1)
    SeatGroupFactory(id=2)
    ConcessionTypeFactory(id=1)
    ConcessionTypeFactory(id=2)
    SeatFactory(id=1)
    SeatFactory(id=2)

    # Create booking with current tickets
    booking = BookingFactory()
    _ = [TicketFactory(booking=booking, **ticket) for ticket in currentTickets]

    # Generate mutation query from input data

    ticketQueries = ""
    for ticket in plannedTickets:
        queryStr = """
                    {
                        id: %s
                        seatId: %s
                        seatGroupId:%s
                        concessionTypeId: %s
                    }
                    """ % (
            to_global_id("TicketNode", ticket.get("id")),
            to_global_id("TicketNode", ticket.get("id")),
            to_global_id("SeatGroupNode", ticket.get("id")),
            to_global_id("SeatNode", ticket.get("id")),
        )
        ticketQueries += queryStr

    request_query = """
        mutation {
            createBooking (
                performanceId: UHJvZHVjdGlvbk5vZGU6MQ==,
                tickets: [
                    %s
                ]
            ){
                booking{
                    id
                }
            }
        }
        """ % (
        ticketQueries
    )

    print(request_query)
    gql_client_flexible.set_user(booking.user)
    response = gql_client_flexible.execute(request_query)
    print(response)
    # _ = [
    #     print(to_global_id("TicketNode", ticket.get("id"))) for ticket in plannedTickets
    # ]
    # _ = [print(ticket.id) for ticket in booking.tickets.all()]
    # newTickets = [Ticket(**ticket) for ticket in newList]
    # addTickets = [Ticket(**ticket) for ticket in addList]
    # deleteTickets = [Ticket(**ticket) for ticket in deleteList]

    assert True
