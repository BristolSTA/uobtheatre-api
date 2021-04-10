import pytest
from graphql_relay.node.node import from_global_id, to_global_id

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
from uobtheatre.utils.test_utils import ticketDictListDictGen, ticketListDictGen
from uobtheatre.venues.test.factories import SeatFactory, SeatGroupFactory


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
                                "status": "IN_PROGRESS",
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
            success
            errors {
              __typename
              ... on NonFieldError {
                message
                code
              }
            }
         }
        }
    """

    client = gql_client_flexible
    response = client.execute(request % data)

    if not is_valid:
        assert response.get("errors") or (
            response["data"]["createBooking"]["errors"]
            and not response["data"]["createBooking"]["success"]
        )
    else:
        assert (
            not response.get("errors")
            and response["data"]["createBooking"]["success"]
            and response["data"]["createBooking"]["errors"] is None
        )


@pytest.mark.django_db
def test_booking_inprogress(gql_client_flexible, gql_id):
    """
    We will often want to get an "inprogress" booking for a given booking and user.
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
    "currentTickets, plannedTickets, expectedTickets",
    [
        # No change in tickets
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
        # Create a new ticket
        (
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                    "id": 1,
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
                },
            ],
        ),
        # Delete all tickets
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
            [],
            [],
        ),
        # All new tickets
        (
            [],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
            ],
            [
                {
                    "seat_group_id": 2,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
            ],
        ),
        # Add a similar ticket
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
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
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
                {
                    "seat_group_id": 1,
                    "concession_type_id": 1,
                    "seat_id": 1,
                },
            ],
        ),
    ],
)
def test_update_booking(
    currentTickets, plannedTickets, expectedTickets, gql_client_flexible
):

    seat_group_1 = SeatGroupFactory(id=1)
    seat_group_2 = SeatGroupFactory(id=2)
    ConcessionTypeFactory(id=1)
    ConcessionTypeFactory(id=2)
    SeatFactory(id=1)
    SeatFactory(id=2)
    performance = PerformanceFactory()
    PerformanceSeatingFactory(performance=performance, seat_group=seat_group_1)
    PerformanceSeatingFactory(performance=performance, seat_group=seat_group_2)

    # Create booking with current tickets
    booking = BookingFactory(performance=performance)
    _ = [TicketFactory(booking=booking, **ticket) for ticket in currentTickets]
    # Generate mutation query from input data

    ticketQueries = ""
    for ticket in plannedTickets:
        if ticket.get("id") is not None:
            queryStr = """
                        {
                            id: "%s"
                            seatId: "%s"
                            seatGroupId: "%s"
                            concessionTypeId: "%s"
                        }
                        """ % (
                to_global_id("TicketNode", ticket.get("id")),
                to_global_id("SeatNode", ticket.get("seat_id")),
                to_global_id("SeatGroupNode", ticket.get("seat_group_id")),
                to_global_id("ConcessionTypeNode", ticket.get("concession_type_id")),
            )
        else:
            queryStr = """
                        {
                            seatId: "%s"
                            seatGroupId: "%s"
                            concessionTypeId: "%s"
                        }
                        """ % (
                to_global_id("SeatNode", ticket.get("seat_id")),
                to_global_id("SeatGroupNode", ticket.get("seat_group_id")),
                to_global_id("ConcessionTypeNode", ticket.get("concession_type_id")),
            )
        ticketQueries += queryStr

    request_query = """
        mutation {
            updateBooking (
                bookingId: "%s"
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
        to_global_id("BookingNode", booking.id),
        ticketQueries,
    )

    gql_client_flexible.set_user(booking.user)
    response = gql_client_flexible.execute(request_query)

    return_booking_id = response["data"]["updateBooking"]["booking"]["id"]

    local_booking_id = int(from_global_id(return_booking_id)[1])

    returned_booking = Booking.objects.get(id=local_booking_id)

    expected_booking_tickets = ticketDictListDictGen(expectedTickets)
    updated_booking_tickets = ticketListDictGen(returned_booking.tickets.all())

    assert updated_booking_tickets == expected_booking_tickets


@pytest.mark.django_db
def test_update_booking_capacity_error(gql_client_flexible):

    seat_group = SeatGroupFactory()
    concession_type = ConcessionTypeFactory()
    booking = BookingFactory(user=gql_client_flexible.get_user())
    request_query = """
        mutation {
            updateBooking (
                bookingId: "%s"
                tickets: [
                  {
                    seatGroupId: "%s"
                    concessionTypeId: "%s"
                  }
                ]
            ){
                booking{
                    id
                }
                success
                errors {
                  __typename
                  ... on NonFieldError {
                    message
                    code
                  }
                }
            }
        }
        """ % (
        to_global_id("BookingNode", booking.id),
        to_global_id("SeatGroupNode", seat_group.id),
        to_global_id("ConcessionTypeNode", concession_type.id),
    )
    response = gql_client_flexible.execute(request_query)

    print(response)
    assert response == {
        "data": {
            "updateBooking": {
                "booking": None,
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": f"You cannot book a seat group that is not assigned to this performance, you have booked {seat_group} but the performance only has ",
                        "code": "400",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_create_booking_capacity_error(gql_client_flexible):

    seat_group = SeatGroupFactory()
    concession_type = ConcessionTypeFactory()
    booking = BookingFactory(user=gql_client_flexible.get_user())
    request_query = """
        mutation {
            createBooking (
                performanceId: "%s"
                tickets: [
                  {
                    seatGroupId: "%s"
                    concessionTypeId: "%s"
                  }
                ]
            ){
                booking{
                    id
                }
                success
                errors {
                  __typename
                  ... on NonFieldError {
                    message
                    code
                  }
                }
            }
        }
        """ % (
        to_global_id("PerformanceNode", booking.performance.id),
        to_global_id("SeatGroupNode", seat_group.id),
        to_global_id("ConcessionTypeNode", concession_type.id),
    )
    response = gql_client_flexible.execute(request_query)

    print(response)
    assert response == {
        "data": {
            "createBooking": {
                "booking": None,
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": f"You cannot book a seat group that is not assigned to this performance, you have booked {seat_group} but the performance only has ",
                        "code": "400",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_mutation_wrong_price(gql_client_flexible, gql_id):
    booking = BookingFactory()

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 102
            nonce: "cnon:card-nonce-ok"
        ) {
            success
            errors {
              __typename
              ... on NonFieldError {
                message
                code
              }
            }
          }
        }
    """
    response = gql_client_flexible.execute(
        request_query % gql_id(booking.id, "BookingNode")
    )
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "The booking price does not match the expected price",
                        "code": None,
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_square_error(mock_square, gql_client_flexible, gql_id):
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    client = gql_client_flexible

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 0
            nonce: "cnon:card-nonce-ok"
        ) {
            success
            errors {
              __typename
              ... on NonFieldError {
                message
                code
              }
            }
          }
        }
    """

    mock_square.reason_phrase = "Some phrase"
    mock_square.status_code = 400
    mock_square.success = False

    response = client.execute(request_query % gql_id(booking.id, "BookingNode"))
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "Some phrase",
                        "code": "400",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_mutation_payed_booking(gql_client_flexible, gql_id):
    booking = BookingFactory(status=Booking.BookingStatus.PAID)
    client = gql_client_flexible

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 0
            nonce: "cnon:card-nonce-ok"
        ) {
            success
            errors {
              __typename
              ... on NonFieldError {
                message
                code
              }
            }
          }
        }
    """
    response = client.execute(request_query % gql_id(booking.id, "BookingNode"))
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "The booking is not in progress",
                        "code": None,
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_success(mock_square, gql_client_flexible, gql_id):
    booking = BookingFactory(status=Booking.BookingStatus.IN_PROGRESS)
    client = gql_client_flexible

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 0
            nonce: "cnon:card-nonce-ok"
        ) {
            success
            errors {
              __typename
            }

            booking {
              status
              payments {
                edges {
                  node {
                    id
                  }
                }
              }
            }

            payment {
              last4
              cardBrand
              provider
              currency
              value
            }
          }
        }
    """

    mock_square.body = {
        "payment": {
            "id": "abc",
            "card_details": {
                "card": {
                    "card_brand": "VISA",
                    "last_4": "1111",
                }
            },
            "amount_money": {
                "currency": "GBP",
                "amount": 0,
            },
        }
    }
    mock_square.success = True

    response = client.execute(request_query % gql_id(booking.id, "BookingNode"))
    assert response == {
        "data": {
            "payBooking": {
                "booking": {
                    "status": "PAID",
                    "payments": {
                        "edges": [
                            {
                                "node": {
                                    "id": gql_id(
                                        booking.payments.first().id, "PaymentNode"
                                    )
                                }
                            }
                        ]
                    },
                },
                "payment": {
                    "last4": "1111",
                    "cardBrand": "VISA",
                    "provider": "SQUARE_ONLINE",
                    "currency": "GBP",
                    "value": 0,
                },
                "success": True,
                "errors": None,
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "performance_id, booking_obj, check_in_ticket_id_list, not_check_in_ticket_id_list, non_booking_ticket_id_list",
    [
        (1, {"booking_id": 1, "performance_id": 1}, [1, 2, 3], [4, 5, 6], []),
        (1, {"booking_id": 2, "performance_id": 1}, [1, 2, 3], [], []),
        (2, {"booking_id": 3, "performance_id": 1}, [1, 2, 3], [], []),
        (1, {"booking_id": 4, "performance_id": 1}, [1, 2, 3], [], [4, 5, 6]),
        (1, {"booking_id": 4, "performance_id": 1}, [], [], [7, 8, 9]),
        (1, {"booking_id": 4, "performance_id": 2}, [1, 2, 3], [], [4, 5, 6]),
    ],
)
def test_check_in_booking(
    performance_id,
    booking_obj,
    check_in_ticket_id_list,
    not_check_in_ticket_id_list,
    non_booking_ticket_id_list,
    gql_client_flexible,
):

    """
    What are we testing?
    that only the expected tickets are checked in
    that incorrect ticket refs are not checked in
    """

    if booking_obj.get("performance_id") == performance_id:
        performance = PerformanceFactory(id=performance_id)
        booking = BookingFactory(
            id=booking_obj.get("booking_id"),
            performance=performance,
            user=gql_client_flexible.get_user(),
        )
    else:
        booking_performance = PerformanceFactory(id=booking_obj.get("performance_id"))
        performance = PerformanceFactory(id=performance_id)
        booking = BookingFactory(
            id=booking_obj.get("booking_id"),
            performance=booking_performance,
            user=gql_client_flexible.get_user(),
        )
    non_booking = BookingFactory(
        id=0,
        performance=performance,
        user=gql_client_flexible.get_user(),
    )

    # Expected to check in and pass
    check_in_tickets = []
    for ticket_id in check_in_ticket_id_list:
        check_in_tickets.append(TicketFactory(id=ticket_id, booking=booking))

    # Tickets are not to be checked in, expect as much
    not_check_in_tickets = []
    for ticket_id in not_check_in_ticket_id_list:
        not_check_in_tickets.append(TicketFactory(id=ticket_id, booking=booking))

    # As these are not part of the correct booking expected to fail
    non_booking_tickets = []
    for ticket_id in non_booking_ticket_id_list:
        non_booking_tickets.append(TicketFactory(id=ticket_id, booking=non_booking))

    for ticket in check_in_tickets:
        assert ticket.checked_in == False

    for ticket in not_check_in_tickets:
        assert ticket.checked_in == False

    for ticket in non_booking_tickets:
        assert ticket.checked_in == False

    ticketQueries = ""
    for ticket in check_in_tickets:
        queryStr = """
                    {
                        ticketId: "%s"
                    }
                    """ % (
            to_global_id("TicketNode", ticket.id),
        )
        ticketQueries += queryStr

    for ticket in non_booking_tickets:
        queryStr = """
                    {
                        ticketId: "%s"
                    }
                    """ % (
            to_global_id("TicketNode", ticket.id),
        )
        ticketQueries += queryStr

    request_query = """
        mutation {
            checkInBooking (
                bookingReference: "%s"
                performanceId: "%s"
                tickets: [
                    %s
                ]
            ){
                success
                errors {
                __typename
                }
                booking{
                    id
                }
            }
        }
        """ % (
        booking.reference,
        to_global_id("PerformanceNode", performance.id),
        ticketQueries,
    )

    response = gql_client_flexible.execute(request_query)

    # If there are no wrong booking tickets - and the booking performance matches the request performance
    # we are expecting all check in tickets to be checked in and all other tickets to be left unchecked
    if (
        len(non_booking_tickets) == 0
        and booking_obj.get("performance_id") == performance_id
    ):
        # In this instance we expect success and a correctly returned booking.
        assert response["data"]["checkInBooking"]["success"] == True
        assert response["data"]["checkInBooking"]["errors"] == None

        return_booking_id = response["data"]["checkInBooking"]["booking"]["id"]
        local_booking_id = int(from_global_id(return_booking_id)[1])
        assert local_booking_id == booking_obj.get("booking_id")

        for ticket in check_in_tickets:
            ticket.refresh_from_db()
            assert ticket.checked_in == True
    else:
        # In the instance where the performance is not correct or there are tickets for the wrong booking we expect failure and a returned Field Error
        assert response["data"]["checkInBooking"]["success"] == False
        assert len(response["data"]["checkInBooking"]["errors"]) == 1

        assert (
            response["data"]["checkInBooking"]["errors"][0]["__typename"]
            == "FieldError"
        )

        assert response["data"]["checkInBooking"]["booking"] == None

        for ticket in check_in_tickets:
            ticket.refresh_from_db()
            assert ticket.checked_in == False

    # either way we expect no tickets from the non_check_in and non_booking lists to be changed
    for ticket in not_check_in_tickets:
        ticket.refresh_from_db()
        assert ticket.checked_in == False

    for ticket in non_booking_tickets:
        ticket.refresh_from_db()
        assert ticket.checked_in == False
