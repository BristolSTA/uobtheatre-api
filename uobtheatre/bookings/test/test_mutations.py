# pylint: disable=too-many-lines
import pytest
from graphql_relay.node.node import from_global_id, to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
)
from uobtheatre.discounts.test.factories import ConcessionTypeFactory
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.test_utils import ticket_dict_list_dict_gen, ticket_list_dict_gen
from uobtheatre.venues.test.factories import SeatFactory, SeatGroupFactory


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
        # TODO For now concession # pylint: disable=fixme
        # type is required as there is no default, but when this is not the
        # case we need to check adult is default.
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
def test_create_booking_with_taget_user_without_perms(gql_client_flexible):

    psg = PerformanceSeatingFactory()
    request = """
        mutation {
          createBooking(
            performanceId: "%s"
            targetUser: "abc@email.com"
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
    """ % to_global_id(
        "PerformanceNode", psg.performance.id
    )

    response = gql_client_flexible.execute(request)
    assert response["data"]["createBooking"]["success"] is False
    assert response["data"]["createBooking"]["errors"] == [
        {
            "__typename": "NonFieldError",
            "message": "You do not have permission to create a booking for another user.",
            "code": "403",
        }
    ]


@pytest.mark.django_db
def test_create_booking_with_taget_user(gql_client_flexible):

    user = UserFactory(email="abc@email.com")
    psg = PerformanceSeatingFactory()
    request = """
        mutation {
          createBooking(
            performanceId: "%s"
            targetUser: "abc@email.com"
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
    """ % to_global_id(
        "PerformanceNode", psg.performance.id
    )

    assign_perm("boxoffice", gql_client_flexible.user, psg.performance.production)
    response = gql_client_flexible.execute(request)

    assert response["data"]["createBooking"]["success"] is True
    booking = Booking.objects.first()
    assert str(booking.user.id) == str(user.id)
    assert str(booking.creator.id) == str(gql_client_flexible.user.id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "current_tickets, planned_tickets, expected_tickets",
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
                },  # pylint: disable=too-many-locals
            ],
        ),
    ],
)
def test_update_booking(
    current_tickets, planned_tickets, expected_tickets, gql_client_flexible
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
    _ = [TicketFactory(booking=booking, **ticket) for ticket in current_tickets]
    # Generate mutation query from input data

    ticket_queries = ""
    for ticket in planned_tickets:
        if ticket.get("id") is not None:
            query_str = """
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
            query_str = """
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
        ticket_queries += query_str

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
        ticket_queries,
    )

    gql_client_flexible.user = booking.user
    response = gql_client_flexible.execute(request_query)

    return_booking_id = response["data"]["updateBooking"]["booking"]["id"]

    local_booking_id = int(from_global_id(return_booking_id)[1])

    returned_booking = Booking.objects.get(id=local_booking_id)

    expected_booking_tickets = ticket_dict_list_dict_gen(expected_tickets)
    updated_booking_tickets = ticket_list_dict_gen(returned_booking.tickets.all())

    assert updated_booking_tickets == expected_booking_tickets


@pytest.mark.django_db
def test_update_booking_no_tickets(gql_client_flexible):
    booking = BookingFactory(user=gql_client_flexible.user)
    tickets = [TicketFactory(booking=booking) for _ in range(10)]

    request_query = """
        mutation {
            updateBooking (
                bookingId: "%s"
            ){
                booking{
                    id
                }
            }
        }
        """ % (
        to_global_id("BookingNode", booking.id),
    )

    gql_client_flexible.execute(request_query)

    # Assert the bookings ticket have not changed
    assert set(booking.tickets.all()) == set(tickets)


@pytest.mark.django_db
def test_update_booking_capacity_error(gql_client_flexible):

    seat_group = SeatGroupFactory()
    concession_type = ConcessionTypeFactory()
    booking = BookingFactory(user=gql_client_flexible.user)
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
    booking = BookingFactory(user=gql_client_flexible.user)
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
              status {
                value
              }
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
              provider {
                value
              }
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
                    "status": {
                        "value": "PAID",
                    },
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
                    "provider": {
                        "value": "SQUARE_ONLINE",
                    },
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
    ],  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
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
            user=gql_client_flexible.user,
        )
    else:
        booking_performance = PerformanceFactory(id=booking_obj.get("performance_id"))
        performance = PerformanceFactory(id=performance_id)
        booking = BookingFactory(
            id=booking_obj.get("booking_id"),
            performance=booking_performance,
            user=gql_client_flexible.user,
        )
    non_booking = BookingFactory(
        id=0,
        performance=performance,
        user=gql_client_flexible.user,
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
        assert not ticket.checked_in

    for ticket in not_check_in_tickets:
        assert not ticket.checked_in

    for ticket in non_booking_tickets:
        assert not ticket.checked_in

    ticket_queries = ""
    for ticket in check_in_tickets:
        query_str = """
                    {
                        ticketId: "%s"
                    }
                    """ % (
            to_global_id("TicketNode", ticket.id),
        )
        ticket_queries += query_str

    for ticket in non_booking_tickets:
        query_str = """
                    {
                        ticketId: "%s"
                    }
                    """ % (
            to_global_id("TicketNode", ticket.id),
        )
        ticket_queries += query_str

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
        ticket_queries,
    )

    response = gql_client_flexible.execute(request_query)

    # If there are no wrong booking tickets - and the booking performance
    # matches the request performance we are expecting all check in tickets to
    # be checked in and all other tickets to be left unchecked
    if (
        len(non_booking_tickets) == 0
        and booking_obj.get("performance_id") == performance_id
    ):
        # In this instance we expect success and a correctly returned booking.
        assert response["data"]["checkInBooking"]["success"]
        assert response["data"]["checkInBooking"]["errors"] is None

        return_booking_id = response["data"]["checkInBooking"]["booking"]["id"]
        local_booking_id = int(from_global_id(return_booking_id)[1])
        assert local_booking_id == booking_obj.get("booking_id")

        for ticket in check_in_tickets:
            ticket.refresh_from_db()
            assert ticket.checked_in
    elif booking_obj.get("performance_id") == performance_id:
        # The instance where there are tickets that don't belong to the booking
        assert len(response["data"]["checkInBooking"]["errors"]) == len(
            non_booking_ticket_id_list
        )
        assert (
            response["data"]["checkInBooking"]["errors"][0]["__typename"]
            == "FieldError"
        )
    else:
        # In the instance where the performance is not correct or there are
        # tickets for the wrong booking we expect failure and a returned Field
        # Error
        assert not response["data"]["checkInBooking"]["success"]
        assert len(response["data"]["checkInBooking"]["errors"]) == 1

        assert (
            response["data"]["checkInBooking"]["errors"][0]["__typename"]
            == "FieldError"
        )

        assert response["data"]["checkInBooking"]["booking"] is None

        for ticket in check_in_tickets:
            ticket.refresh_from_db()
            assert not ticket.checked_in

    # either way we expect no tickets from the non_check_in and non_booking lists to be changed
    for ticket in not_check_in_tickets:
        ticket.refresh_from_db()
        assert not ticket.checked_in

    for ticket in non_booking_tickets:
        ticket.refresh_from_db()
        assert not ticket.checked_in


@pytest.mark.django_db
def test_check_in_booking_fails_if_already_checked_in(gql_client_flexible):
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance,
        user=gql_client_flexible.user,
    )

    checked_in_ticket = TicketFactory(booking=booking, checked_in=True)

    request_query = """
    mutation {
    checkInBooking(
            bookingReference: "%s"
            performanceId: "%s"
            tickets: [
                { ticketId: "%s"}
            ]
        ) {
            success
            errors {
            __typename
            ... on NonFieldError {
                message
            }
            }
        }
    }
    """
    response = gql_client_flexible.execute(
        request_query
        % (
            booking.reference,
            to_global_id("PerformanceNode", performance.id),
            to_global_id("TicketNode", checked_in_ticket.id),
        )
    )
    assert response == {
        "data": {
            "checkInBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "Ticket {} is already checked in".format(
                            checked_in_ticket.id
                        ),
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_uncheck_in_booking(gql_client_flexible):
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance,
        user=gql_client_flexible.user,
    )

    checked_in_ticket = TicketFactory(booking=booking, checked_in=True)
    unchecked_in_ticket = TicketFactory(booking=booking, checked_in=False)

    request_query = """
    mutation {
    uncheckInBooking(
            bookingReference: "%s"
            performanceId: "%s"
            tickets: [
                { ticketId: "%s"},
                { ticketId: "%s"}
            ]
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
        request_query
        % (
            booking.reference,
            to_global_id("PerformanceNode", performance.id),
            to_global_id("TicketNode", checked_in_ticket.id),
            to_global_id("TicketNode", unchecked_in_ticket.id),
        )
    )
    assert response == {"data": {"uncheckInBooking": {"success": True, "errors": None}}}


@pytest.mark.django_db
def test_uncheck_in_booking_incorrect_performance(gql_client_flexible):
    performance = PerformanceFactory()
    wrong_performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance,
        user=gql_client_flexible.user,
    )

    checked_in_ticket = TicketFactory(booking=booking, checked_in=True)

    request_query = """
    mutation {
    uncheckInBooking(
            bookingReference: "%s"
            performanceId: "%s"
            tickets: [
                { ticketId: "%s"}
            ]
        ) {
            success
                errors {
                __typename
                ... on NonFieldError {
                    message
                }
                ... on FieldError {
                    message
                }
            }
        }
    }
    """
    response = gql_client_flexible.execute(
        request_query
        % (
            booking.reference,
            to_global_id("PerformanceNode", wrong_performance.id),
            to_global_id("TicketNode", checked_in_ticket.id),
        )
    )
    assert response == {
        "data": {
            "uncheckInBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "The booking performance does not match the given performance.",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_uncheck_in_booking_incorrect_ticket(gql_client_flexible):
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance,
        user=gql_client_flexible.user,
    )
    incorrect_booking = BookingFactory(
        performance=performance,
        user=gql_client_flexible.user,
    )

    checked_in_ticket = TicketFactory(booking=incorrect_booking, checked_in=True)

    request_query = """
    mutation {
    uncheckInBooking(
            bookingReference: "%s"
            performanceId: "%s"
            tickets: [
                { ticketId: "%s"}
            ]
        ) {
            success
                errors {
                __typename
                ... on NonFieldError {
                    message
                }
                ... on FieldError {
                    message
                }
            }
        }
    }
    """
    response = gql_client_flexible.execute(
        request_query
        % (
            booking.reference,
            to_global_id("PerformanceNode", booking.performance.id),
            to_global_id("TicketNode", checked_in_ticket.id),
        )
    )
    assert response == {
        "data": {
            "uncheckInBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": f"The booking of ticket {checked_in_ticket.id} does not match the given booking.",
                    }
                ],
            }
        }
    }
