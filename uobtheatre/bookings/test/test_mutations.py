# pylint: disable=too-many-lines


from datetime import timedelta

import pytest
from django.utils import timezone
from graphql_relay.node.node import from_global_id, to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.mutations import PayBooking, parse_target_user_email
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
    add_ticket_to_booking,
)
from uobtheatre.discounts.test.factories import ConcessionTypeFactory
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.transaction_providers import SquareOnline, SquarePOS
from uobtheatre.productions.test.factories import PerformanceFactory
from uobtheatre.users.models import User
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.exceptions import AuthorizationException, GQLException
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
    data, seat_group_capacity, performance_capacity, is_valid, gql_client
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

    gql_client.login()
    response = gql_client.execute(request % data)

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
def test_create_booking_deletes_users_draft(gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    PerformanceSeatingFactory(performance=performance)

    assert Booking.objects.count() == 0  # Check that no bookings exist

    BookingFactory(
        performance=performance,
        user=gql_client.user,
        status=Payable.PayableStatus.IN_PROGRESS,
    )  # A booking belonging to this user
    unaffected_booking = BookingFactory(
        performance=performance, status=Payable.PayableStatus.IN_PROGRESS
    )  # A booking belonging to another user

    assert Booking.objects.count() == 2

    request = """
        mutation {
          createBooking(
            performanceId: "%s"
          ) {
            success
            errors {
              __typename
              ... on NonFieldError {
                message
              }
            }
            booking {
                id
            }
         }
        }
    """ % to_global_id(
        "PerformanceNode", performance.id
    )

    response = gql_client.execute(request)

    assert Booking.objects.count() == 2
    assert [booking.id for booking in Booking.objects.all()].sort() == [
        int(from_global_id(response["data"]["createBooking"]["booking"]["id"])[1]),
        unaffected_booking.id,
    ].sort()


@pytest.mark.django_db
@pytest.mark.parametrize("with_boxoffice_perms", [False, True])
def test_create_booking_with_too_many_tickets(gql_client, with_boxoffice_perms):
    performance = PerformanceFactory(id=1, capacity=100)
    seat_group = SeatGroupFactory(id=1)
    PerformanceSeatingFactory(
        performance=performance, seat_group=seat_group, capacity=100
    )
    concession_type = ConcessionTypeFactory()

    request = """
        mutation {{
          createBooking(
            performanceId: "{0}"
            tickets: [
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
            ]
          ) {{
            success
            errors {{
              __typename
              ... on NonFieldError {{
                message
              }}
            }}
         }}
        }}
    """.format(
        to_global_id("PerformanceNode", performance.id),
        to_global_id("SeatGroupNode", seat_group.id),
        to_global_id("ConcessionType", concession_type.id),
    )

    gql_client.login()
    if with_boxoffice_perms:
        assign_perm("boxoffice", gql_client.user, performance.production)

    response = gql_client.execute(request)

    assert response["data"]["createBooking"]["success"] is with_boxoffice_perms

    if not with_boxoffice_perms:
        assert (
            response["data"]["createBooking"]["errors"][0]["message"]
            == "You may only book a maximum of 10 tickets"
        )


@pytest.mark.django_db
def test_cant_create_booking_with_unbookable_performance(gql_client):
    performance = PerformanceFactory(end=(timezone.now() - timedelta(days=1)))
    request = """
        mutation{
            createBooking(performanceId: "%s") {
                success
                errors {
                    ... on NonFieldError {
                        message
                    }
                }
            }
        }
    """ % to_global_id(
        "PerformanceNode", performance.id
    )

    gql_client.login()
    response = gql_client.execute(request)

    assert response["data"]["createBooking"]["success"] is False
    assert (
        response["data"]["createBooking"]["errors"][0]["message"]
        == "This performance is not able to be booked at the moment"
    )


@pytest.mark.django_db
def test_create_booking_with_taget_user_without_perms(gql_client):

    psg = PerformanceSeatingFactory()
    request = """
        mutation {
          createBooking(
            performanceId: "%s"
            targetUserEmail: "abc@email.com"
          ) {
            booking {
              id
            }
            success
            errors {
              __typename
              ... on FieldError {
                message
                code
                field
              }
            }
         }
        }
    """ % to_global_id(
        "PerformanceNode", psg.performance.id
    )

    gql_client.login()
    response = gql_client.execute(request)
    assert response["data"]["createBooking"]["success"] is False
    assert response["data"]["createBooking"]["errors"] == [
        {
            "__typename": "FieldError",
            "message": "You do not have permission to create a booking for another user.",
            "code": "403",
            "field": "targetUserEmail",
        }
    ]


@pytest.mark.django_db
def test_create_booking_with_taget_user(gql_client):

    user = UserFactory(email="abc@email.com")
    psg = PerformanceSeatingFactory()
    request = """
        mutation {
          createBooking(
            performanceId: "%s"
            targetUserEmail: "abc@email.com"
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

    assign_perm("boxoffice", gql_client.login().user, psg.performance.production)
    response = gql_client.execute(request)

    assert response["data"]["createBooking"]["success"] is True
    booking = Booking.objects.first()
    assert str(booking.user.id) == str(user.id)
    assert str(booking.creator.id) == str(gql_client.user.id)


@pytest.mark.django_db
def test_create_booking_with_new_taget_user(gql_client):

    psg = PerformanceSeatingFactory()
    request = """
        mutation {
          createBooking(
            performanceId: "%s"
            targetUserEmail: "abc@email.com"
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

    assign_perm("boxoffice", gql_client.login().user, psg.performance.production)
    response = gql_client.execute(request)

    assert response["data"]["createBooking"]["success"] is True

    # Assert new user created
    assert User.objects.filter(email="abc@email.com").exists()

    booking = Booking.objects.first()
    assert booking.user.email == "abc@email.com"
    assert str(booking.creator.id) == str(gql_client.user.id)


@pytest.mark.django_db
def test_create_booking_admin_discount_without_perms(gql_client):
    performance = PerformanceFactory()
    PerformanceSeatingFactory(performance=performance)
    request = """
        mutation {
          createBooking(
            performanceId: "%s"
            adminDiscountPercentage: 0.8
          ) {
            booking {
              id
            }
            success
            errors {
              __typename
              ... on FieldError {
                message
                field
              }
            }
         }
        }
    """ % to_global_id(
        "PerformanceNode", performance.id
    )
    gql_client.login()
    response = gql_client.execute(request)

    assert response["data"]["createBooking"]["success"] is False
    assert (
        response["data"]["createBooking"]["errors"][0]["message"]
        == "You do not have permission to assign an admin discount"
    )
    assert (
        response["data"]["createBooking"]["errors"][0]["field"]
        == "adminDiscountPercentage"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "discount,should_be_valid",
    [
        (0.8, True),
        (-1, False),
        (1.2, False),
    ],
)
def test_create_booking_admin_discount(gql_client, discount, should_be_valid):
    performance = PerformanceFactory()
    PerformanceSeatingFactory(performance=performance)
    request = """
        mutation {
          createBooking(
            performanceId: "%s"
            adminDiscountPercentage: %s
          ) {
            booking {
              id
              adminDiscountPercentage
            }
            success
            errors {
              __typename
              ... on FieldError {
                message
                field
              }
            }
         }
        }
    """ % (
        to_global_id("PerformanceNode", performance.id),
        discount,
    )
    gql_client.login()
    assign_perm("change_production", gql_client.user, performance.production)
    response = gql_client.execute(request)

    assert response["data"]["createBooking"]["success"] is should_be_valid

    if not should_be_valid:
        assert (
            response["data"]["createBooking"]["errors"][0]["field"]
            == "adminDiscountPercentage"
        )
    else:
        assert (
            response["data"]["createBooking"]["booking"]["adminDiscountPercentage"]
            == 0.8
        )


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
def test_update_booking(current_tickets, planned_tickets, expected_tickets, gql_client):

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
    booking = BookingFactory(
        performance=performance, status=Payable.PayableStatus.IN_PROGRESS
    )
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

    gql_client.user = booking.user
    response = gql_client.execute(request_query)

    return_booking_id = response["data"]["updateBooking"]["booking"]["id"]

    local_booking_id = int(from_global_id(return_booking_id)[1])

    returned_booking = Booking.objects.get(id=local_booking_id)

    expected_booking_tickets = ticket_dict_list_dict_gen(expected_tickets)
    updated_booking_tickets = ticket_list_dict_gen(returned_booking.tickets.all())

    assert updated_booking_tickets == expected_booking_tickets


@pytest.mark.django_db
def test_update_expired_booking(gql_client):
    gql_client.login()
    booking = BookingFactory(
        user=gql_client.user,
        expires_at=timezone.now() - timedelta(minutes=20),
        status=Payable.PayableStatus.IN_PROGRESS,
    )

    request = """
        mutation {
          updateBooking(
            bookingId: "%s"
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
    """ % to_global_id(
        "BookingNode", booking.id
    )

    response = gql_client.execute(request)

    assert response["data"]["updateBooking"]["success"] is False
    assert (
        response["data"]["updateBooking"]["errors"][0]["message"]
        == "This booking has expired. Please create a new booking."
    )


@pytest.mark.django_db
@pytest.mark.parametrize("with_boxoffice_perms", [False, True])
def test_update_booking_with_too_many_tickets(gql_client, with_boxoffice_perms):
    gql_client.login()
    performance = PerformanceFactory(id=1, capacity=100)
    booking = BookingFactory(
        performance=performance,
        user=gql_client.user,
        status=Payable.PayableStatus.IN_PROGRESS,
    )
    seat_group = SeatGroupFactory(id=1)
    PerformanceSeatingFactory(
        performance=performance, seat_group=seat_group, capacity=100
    )
    concession_type = ConcessionTypeFactory()
    TicketFactory(
        booking=booking, seat_group=seat_group, concession_type=concession_type
    )  # 3 exisiting tickets
    TicketFactory(
        booking=booking, seat_group=seat_group, concession_type=concession_type
    )
    TicketFactory(
        booking=booking, seat_group=seat_group, concession_type=concession_type
    )

    request = """
        mutation {{
          updateBooking(
            bookingId: "{0}"
            tickets: [
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
                {{seatGroupId: "{1}", concessionTypeId: "{2}"}},
            ]
          ) {{
            success
            errors {{
              __typename
              ... on NonFieldError {{
                message
              }}
            }}
         }}
        }}
    """.format(
        to_global_id("BookingNode", booking.id),
        to_global_id("SeatGroupNode", seat_group.id),
        to_global_id("ConcessionType", concession_type.id),
    )

    if with_boxoffice_perms:
        assign_perm("boxoffice", gql_client.user, performance.production)

    response = gql_client.execute(request)

    assert response["data"]["updateBooking"]["success"] is with_boxoffice_perms

    if not with_boxoffice_perms:
        assert (
            response["data"]["updateBooking"]["errors"][0]["message"]
            == "You may only book a maximum of 10 tickets"
        )


@pytest.mark.django_db
def test_update_booking_no_tickets(gql_client):
    booking = BookingFactory(user=gql_client.login().user)
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

    gql_client.execute(request_query)

    # Assert the bookings ticket have not changed
    assert set(booking.tickets.all()) == set(tickets)


@pytest.mark.django_db
def test_update_booking_set_target_user(gql_client):
    creator = gql_client.login().user
    booking = BookingFactory(user=creator, status=Payable.PayableStatus.IN_PROGRESS)

    creator.is_superuser = True
    creator.save()

    user = UserFactory(email="user@email.com")
    # Give the user an existing draft booking
    BookingFactory(
        user=user,
        performance=booking.performance,
        status=Payable.PayableStatus.IN_PROGRESS,
    )

    assert creator.bookings.count() == 1
    request_query = """
        mutation {
            updateBooking (
                bookingId: "%s"
                targetUserEmail: "user@email.com"
            ){
                booking{
                    id
                }
            }
        }
        """ % (
        to_global_id("BookingNode", booking.id),
    )

    gql_client.execute(request_query)

    assert creator.bookings.count() == 0
    assert user.bookings.count() == 1
    assert Booking.objects.count() == 1
    assert user.bookings.first().id == booking.id


@pytest.mark.django_db
def test_update_booking_set_target_user_to_same_user(gql_client):

    user = UserFactory(email="user@email.com")
    creator = gql_client.login().user
    booking = BookingFactory(user=user, status=Payable.PayableStatus.IN_PROGRESS)

    creator.is_superuser = True
    creator.save()

    assert user.bookings.count() == 1
    request_query = """
        mutation {
            updateBooking (
                bookingId: "%s"
                targetUserEmail: "user@email.com"
            ){
                booking{
                    id
                }
            }
        }
        """ % (
        to_global_id("BookingNode", booking.id),
    )

    response = gql_client.execute(request_query)

    assert user.bookings.count() == 1
    assert user.bookings.first().id == booking.id
    assert response["data"]["updateBooking"]["booking"]["id"] == to_global_id(
        "BookingNode", booking.id
    )


@pytest.mark.django_db
def test_update_booking_admin_discount_without_perms(gql_client):
    booking = BookingFactory(status=Payable.PayableStatus.IN_PROGRESS)
    request = """
        mutation {
          updateBooking(
            bookingId: "%s"
            adminDiscountPercentage: 0.8
          ) {
            booking {
              id
            }
            success
            errors {
              __typename
              ... on FieldError {
                message
                field
              }
            }
         }
        }
    """ % to_global_id(
        "BookingNode", booking.id
    )
    gql_client.login(booking.user)
    response = gql_client.execute(request)

    assert response["data"]["updateBooking"]["success"] is False
    assert (
        response["data"]["updateBooking"]["errors"][0]["message"]
        == "You do not have permission to assign an admin discount"
    )
    assert (
        response["data"]["updateBooking"]["errors"][0]["field"]
        == "adminDiscountPercentage"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "discount,should_be_valid",
    [
        (0.8, True),
        (-1, False),
        (1.2, False),
    ],
)
def test_update_booking_admin_discount(gql_client, discount, should_be_valid):
    booking = BookingFactory(status=Payable.PayableStatus.IN_PROGRESS)
    request = """
        mutation {
          updateBooking(
            bookingId: "%s"
            adminDiscountPercentage: %s
          ) {
            booking {
              id
              adminDiscountPercentage
            }
            errors{
                ...on FieldError {
                    message
                    field
                }
            }
            success
         }
        }
    """ % (
        to_global_id("BookingNode", booking.id),
        discount,
    )
    gql_client.login(booking.user)
    assign_perm("change_production", gql_client.user, booking.performance.production)
    response = gql_client.execute(request)

    assert response["data"]["updateBooking"]["success"] is should_be_valid

    if not should_be_valid:
        assert (
            response["data"]["updateBooking"]["errors"][0]["field"]
            == "adminDiscountPercentage"
        )
    else:
        assert (
            response["data"]["updateBooking"]["booking"]["adminDiscountPercentage"]
            == 0.8
        )


@pytest.mark.django_db
def test_update_booking_without_permission(gql_client):
    booking = BookingFactory(status=Payable.PayableStatus.IN_PROGRESS)

    request_query = """
        mutation {
            updateBooking (
                bookingId: "%s"
            ){
                booking{
                    id
                }
                errors {
                  ... on NonFieldError {
                    message
                    code
                  }
                }
            }
        }
        """ % (
        to_global_id("BookingNode", booking.id),
    )

    gql_client.login()
    response = gql_client.execute(request_query)
    assert response == {
        "data": {
            "updateBooking": {
                "booking": None,
                "errors": [
                    {
                        "code": "403",
                        "message": "You do not have permission to access this booking.",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_update_booking_capacity_error(gql_client):

    seat_group = SeatGroupFactory()
    concession_type = ConcessionTypeFactory()
    booking = BookingFactory(
        user=gql_client.login().user, status=Payable.PayableStatus.IN_PROGRESS
    )
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
    response = gql_client.execute(request_query)

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
def test_update_paid_booking_fails(gql_client):

    seat_group = SeatGroupFactory()
    concession_type = ConcessionTypeFactory()
    booking = BookingFactory(
        user=gql_client.login().user, status=Payable.PayableStatus.PAID
    )
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
                success
                errors {
                  __typename
                  ... on NonFieldError {
                    message
                  }
                }
            }
        }
        """ % (
        to_global_id("BookingNode", booking.id),
        to_global_id("SeatGroupNode", seat_group.id),
        to_global_id("ConcessionTypeNode", concession_type.id),
    )
    response = gql_client.execute(request_query)

    assert response == {
        "data": {
            "updateBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "This booking is not in progress, and so cannot be edited",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_booking_with_invalid_seat_group(gql_client):
    gql_client.login()
    seat_group = SeatGroupFactory()
    real_seatgroup = SeatGroupFactory(name="My seat group")
    concession_type = ConcessionTypeFactory()
    booking = BookingFactory(user=gql_client.user)
    PerformanceSeatingFactory(
        performance=booking.performance, seat_group=real_seatgroup, capacity=1
    )
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
    response = gql_client.execute(request_query)

    assert response == {
        "data": {
            "createBooking": {
                "booking": None,
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": f"You cannot book a seat group that is not assigned to this performance, you have booked {seat_group} but the performance only has My seat group",
                        "code": "400",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_mutation_wrong_price(gql_client):
    gql_client.login()
    booking = BookingFactory(
        user=gql_client.user, status=Payable.PayableStatus.IN_PROGRESS
    )

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
    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
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
def test_pay_booking_square_pos_no_device_id(gql_client):
    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 100
            paymentProvider: SQUARE_POS
            idempotencyKey: "my_idempotency_key_string"
        ) {
            success
            errors {
              __typename
              ... on FieldError {
                message
                code
                field
              }
            }
          }
        }
    """
    gql_client.login()
    booking = BookingFactory(status=Payable.PayableStatus.IN_PROGRESS)
    add_ticket_to_booking(booking)

    assign_perm("boxoffice", gql_client.user, booking.performance.production)
    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "A device_id is required when using SQUARE_POS provider.",
                        "code": "missing_required",
                        "field": "deviceId",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_square_error(mock_square, gql_client):
    gql_client.login()
    booking = BookingFactory(
        status=Payable.PayableStatus.IN_PROGRESS, user=gql_client.user
    )
    add_ticket_to_booking(booking)

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 100
            nonce: "cnon:card-nonce-ok"
            idempotencyKey: "my_idempotency_key_string"
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

    with mock_square(
        SquareOnline.client.payments,
        "create_payment",
        success=False,
        reason_phrase="Some phrase",
        status_code=400,
        errors=[{"category": "", "detail": "", "code": "MY_CODE"}],
    ):
        response = gql_client.execute(
            request_query % to_global_id("BookingNode", booking.id)
        )

    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "There was an issue processing your payment (MY_CODE)",
                        "code": "400",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_mutation_unauthorized_provider(gql_client):
    gql_client.login()
    booking = BookingFactory(
        status=Payable.PayableStatus.IN_PROGRESS, user=gql_client.user
    )

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 0
            paymentProvider: CARD
        ) {
            success
            errors {
              __typename
              ... on FieldError {
                message
                code
                field
              }
            }
          }
        }
    """
    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "You do not have permission to pay for a booking with the CARD provider.",
                        "code": "403",
                        "field": "paymentProvider",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_mutation_unauthorized_user(gql_client):
    gql_client.login()
    booking = BookingFactory(status=Payable.PayableStatus.IN_PROGRESS)

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 0
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
    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "You do not have permission to access this booking.",
                        "code": "403",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_mutation_expired_booking(gql_client):
    gql_client.login()
    booking = BookingFactory(
        status=Payable.PayableStatus.IN_PROGRESS,
        user=gql_client.user,
        expires_at=timezone.now() - timedelta(minutes=20),
    )

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 0
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
    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "This booking has expired. Please create a new booking.",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_mutation_online_without_idempotency_key(gql_client):
    gql_client.login()
    booking = BookingFactory(
        status=Payable.PayableStatus.IN_PROGRESS, user=gql_client.user
    )
    add_ticket_to_booking(booking)

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 100
            nonce: "cnon:card-nonce-ok"
        ) {
            success
            errors {
              __typename
              ... on FieldError {
                message
                code
                field
              }
            }
          }
        }
    """
    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "An idempotency key is required when using SQUARE_ONLINE provider.",
                        "code": "missing_required",
                        "field": "idempotencyKey",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_mutation_online_without_nonce(gql_client):
    gql_client.login()
    booking = BookingFactory(
        status=Payable.PayableStatus.IN_PROGRESS, user=gql_client.user
    )
    add_ticket_to_booking(booking)

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 100
            idempotencyKey: "my_idempotency_key_string"
        ) {
            success
            errors {
              __typename
              ... on FieldError {
                message
                code
                field
              }
            }
          }
        }
    """
    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )
    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "A nonce is required when using SQUARE_ONLINE provider.",
                        "code": "missing_required",
                        "field": "nonce",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_success(mock_square, gql_client):
    gql_client.login()
    booking = BookingFactory(
        status=Payable.PayableStatus.IN_PROGRESS, user=gql_client.user
    )
    add_ticket_to_booking(booking)
    ValueMiscCostFactory(value=25)

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 125
            nonce: "cnon:card-nonce-ok"
            idempotencyKey: "my_idempotency_key_string"
        ) {
            success
            errors {
              __typename
            }

            booking {
              status {
                value
              }
              transactions {
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
              providerName {
                value
              }
              currency
              value
              providerFee
              appFee
            }
          }
        }
    """

    with mock_square(
        SquareOnline.client.payments,
        "create_payment",
        body={
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
        },
        success=True,
    ):
        response = gql_client.execute(
            request_query % to_global_id("BookingNode", booking.id)
        )

    assert response == {
        "data": {
            "payBooking": {
                "booking": {
                    "status": {
                        "value": "PAID",
                    },
                    "transactions": {
                        "edges": [
                            {
                                "node": {
                                    "id": to_global_id(
                                        "TransactionNode",
                                        booking.transactions.first().id,
                                    )
                                }
                            }
                        ]
                    },
                },
                "payment": {
                    "last4": "1111",
                    "cardBrand": "VISA",
                    "providerName": {
                        "value": "SQUARE_ONLINE",
                    },
                    "currency": "GBP",
                    "value": 0,
                    "providerFee": None,
                    "appFee": 25,
                },
                "success": True,
                "errors": None,
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_success_square_pos(mock_square, gql_client):
    booking = BookingFactory(status=Payable.PayableStatus.IN_PROGRESS)
    add_ticket_to_booking(booking)
    gql_client.login()
    assign_perm("boxoffice", gql_client.user, booking.performance.production)

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 100
            deviceId: "abc"
            paymentProvider: SQUARE_POS
            idempotencyKey: "my_idempotency_key_string"
        ) {
            success
            errors {
              __typename
            }

            booking {
              status {
                value
              }
              transactions {
                edges {
                  node {
                    id
                  }
                }
              }
            }

            payment {
              providerName {
                value
              }
            }
          }
        }
    """

    with mock_square(
        SquarePOS.client.terminal,
        "create_terminal_checkout",
        body={
            "checkout": {
                "id": "qhpRUp4dPCfqO",
                "amount_money": {"amount": 1000, "currency": "GBP"},
                "device_options": {
                    "device_id": "121CS145A5000029",
                    "tip_settings": {"allow_tipping": False},
                    "skip_receipt_screen": False,
                },
                "status": "PENDING",
                "created_at": "2021-08-13T21:55:20.260Z",
                "updated_at": "2021-08-13T21:55:20.260Z",
                "app_id": "sq0idp-terKoT_PULVOpP8lAJHYQQ",
                "deadline_duration": "PT5M",
                "location_id": "LMHP97T10P8JV",
                "payment_type": "CARD_PRESENT",
            }
        },
        success=True,
    ):
        response = gql_client.execute(
            request_query % to_global_id("BookingNode", booking.id)
        )

    payment = Transaction.objects.first()
    assert response == {
        "data": {
            "payBooking": {
                "booking": {
                    "status": {
                        "value": "IN_PROGRESS",
                    },
                    "transactions": {
                        "edges": [
                            {
                                "node": {
                                    "id": to_global_id("TransactionNode", payment.id)
                                }
                            }
                        ]
                    },
                },
                "payment": {
                    "providerName": {"value": "SQUARE_POS"},
                },
                "success": True,
                "errors": None,
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize("payment_method", ["CARD", "CASH"])
def test_pay_booking_manual(gql_client, payment_method):
    booking = BookingFactory(status=Payable.PayableStatus.IN_PROGRESS)
    add_ticket_to_booking(booking)
    gql_client.login()
    assign_perm("boxoffice", gql_client.user, booking.performance.production)

    request_query = """
    mutation {
	payBooking(
            bookingId: "%s"
            price: 100
            paymentProvider: %s
        ) {
            success
            errors {
              __typename
              ... on NonFieldError {
                message
                code
              }
            }

            booking {
              status {
                value
              }
              transactions {
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
              providerName {
                value
              }
              currency
              value
            }
          }
        }
    """

    response = gql_client.execute(
        request_query % (to_global_id("BookingNode", booking.id), payment_method)
    )

    assert response == {
        "data": {
            "payBooking": {
                "booking": {
                    "status": {
                        "value": "PAID",
                    },
                    "transactions": {
                        "edges": [
                            {
                                "node": {
                                    "id": to_global_id(
                                        "TransactionNode",
                                        booking.transactions.first().id,
                                    )
                                }
                            }
                        ]
                    },
                },
                "payment": {
                    "last4": None,
                    "cardBrand": None,
                    "providerName": {
                        "value": payment_method,
                    },
                    "currency": "GBP",
                    "value": 100,
                },
                "success": True,
                "errors": None,
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_with_no_tickets(gql_client):
    gql_client.login()
    booking = BookingFactory(
        status=Payable.PayableStatus.IN_PROGRESS, user=gql_client.user
    )

    request_query = """
    mutation {
        payBooking(
                bookingId: "%s"
                price: 0
            ) {
                success
                errors {
                    ... on NonFieldError {
                        message
                    }
                }
            }
        }
    """

    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )

    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [{"message": "The booking must have at least one ticket"}],
            }
        }
    }


@pytest.mark.django_db
def test_pay_booking_when_free(gql_client):
    gql_client.login()
    booking = BookingFactory(
        status=Payable.PayableStatus.IN_PROGRESS,
        admin_discount_percentage=1,
        user=gql_client.user,
    )
    add_ticket_to_booking(booking)

    request_query = """
    mutation {
        payBooking(
                bookingId: "%s"
                price: 0
            ) {
                success
                booking {
                    transactions {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                }
            }
        }
    """

    response = gql_client.execute(
        request_query % to_global_id("BookingNode", booking.id)
    )

    assert response == {
        "data": {
            "payBooking": {"success": True, "booking": {"transactions": {"edges": []}}}
        }
    }


@pytest.mark.django_db
def test_paybooking_unsupported_payment_provider(info):
    booking = BookingFactory(status=Payable.PayableStatus.IN_PROGRESS)
    ticket = TicketFactory(booking=booking)
    PerformanceSeatingFactory(
        performance=booking.performance, seat_group=ticket.seat_group
    )
    assign_perm("boxoffice", info.context.user, booking.performance.production)

    with pytest.raises(GQLException) as exc:
        PayBooking.resolve_mutation(
            None, info, booking.id, booking.total, payment_provider="NOT_A_THING"
        )
    assert exc.value.message == "Unsupported payment provider NOT_A_THING."


@pytest.mark.django_db
def test_pay_booking_fails_if_already_paid(gql_client):

    booking = BookingFactory(
        user=gql_client.login().user, status=Payable.PayableStatus.PAID
    )
    request_query = """
        mutation {
            payBooking (
                bookingId: "%s"
                price: 0
            ){
                success
                errors {
                  __typename
                  ... on NonFieldError {
                    message
                  }
                }
            }
        }
        """ % (
        to_global_id("BookingNode", booking.id),
    )
    response = gql_client.execute(request_query)

    assert response == {
        "data": {
            "payBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "This booking has already been paid for",
                    }
                ],
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
    gql_client,
):

    """
    What are we testing?
    that only the expected tickets are checked in
    that incorrect ticket refs are not checked in
    """
    gql_client.login()

    if booking_obj.get("performance_id") == performance_id:
        performance = PerformanceFactory(id=performance_id)
        booking = BookingFactory(
            id=booking_obj.get("booking_id"),
            performance=performance,
            user=gql_client.user,
        )
    else:
        booking_performance = PerformanceFactory(id=booking_obj.get("performance_id"))
        performance = PerformanceFactory(id=performance_id)
        booking = BookingFactory(
            id=booking_obj.get("booking_id"),
            performance=booking_performance,
            user=gql_client.user,
        )
    non_booking = BookingFactory(
        id=0,
        performance=performance,
        user=gql_client.user,
    )

    assign_perm("boxoffice", gql_client.user, performance.production)

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

    response = gql_client.execute(request_query)

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
@pytest.mark.parametrize(
    "status",
    [
        Payable.PayableStatus.IN_PROGRESS,
        Payable.PayableStatus.CANCELLED,
        Payable.PayableStatus.LOCKED,
        Payable.PayableStatus.REFUNDED,
    ],
)
def test_check_in_booking_fails_if_not_paid(gql_client, status):
    performance = PerformanceFactory()
    gql_client.login()
    assign_perm("boxoffice", gql_client.user, performance.production)

    booking = BookingFactory(
        performance=performance, user=gql_client.user, status=status
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
            ... on FieldError {
                message
                field
            }
            }
        }
    }
    """
    response = gql_client.execute(
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
                        "__typename": "FieldError",
                        "field": "bookingReference",
                        "message": "This booking has not been paid for (Status: %s)"
                        % status.label,
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize("prefix", ["check", "uncheck"])
def test_cannot_check_in_booking_without_boxoffice_perm(prefix, gql_client):
    booking = BookingFactory(user=gql_client.login().user)
    request_query = """
    mutation {
      %sInBooking(
        bookingReference: "%s"
        performanceId: "%s"
        tickets: []
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

    response = gql_client.execute(
        request_query
        % (
            prefix,
            booking.reference,
            to_global_id("PerformanceNode", booking.performance.id),
        )
    )

    assert (
        response["data"][f"{prefix}InBooking"]["errors"][0]["message"]
        == f"You do not have permission to {prefix} in this booking."
    )
    assert response == {
        "data": {
            f"{prefix}InBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": f"You do not have permission to {prefix} in this booking.",
                    }
                ],
            }
        }
    }


@pytest.mark.django_db
def test_check_in_booking_fails_if_already_checked_in(gql_client):
    performance = PerformanceFactory()
    gql_client.login()
    assign_perm("boxoffice", gql_client.user, performance.production)

    booking = BookingFactory(performance=performance, user=gql_client.user)

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
    response = gql_client.execute(
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
def test_uncheck_in_booking(gql_client):
    performance = PerformanceFactory()
    gql_client.login()
    assign_perm("boxoffice", gql_client.user, performance.production)

    booking = BookingFactory(performance=performance, user=gql_client.login().user)

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

    gql_client.login()
    assign_perm("boxoffice", gql_client.user, performance.production)
    response = gql_client.execute(
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
def test_uncheck_in_booking_incorrect_performance(gql_client):
    performance = PerformanceFactory()
    wrong_performance = PerformanceFactory()
    booking = BookingFactory(performance=performance, user=gql_client.login().user)

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

    gql_client.login()
    assign_perm("boxoffice", gql_client.user, performance.production)
    assign_perm("boxoffice", gql_client.user, wrong_performance.production)

    response = gql_client.execute(
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
def test_uncheck_in_booking_incorrect_ticket(gql_client):
    performance = PerformanceFactory()
    gql_client.login()

    booking = BookingFactory(performance=performance, user=gql_client.login().user)
    incorrect_booking = BookingFactory(
        performance=performance,
        user=gql_client.user,
    )

    assign_perm("boxoffice", gql_client.user, performance.production)

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
    response = gql_client.execute(
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


@pytest.mark.django_db
def test_parse_target_user_email_get_user():
    creator = UserFactory(is_superuser=True)
    user = UserFactory()
    assert (
        parse_target_user_email(user.email, creator, PerformanceFactory()).id == user.id
    )


@pytest.mark.django_db
def test_parse_target_user_email_creates_user():
    creator = UserFactory(is_superuser=True, email="admin@email.com")

    user = parse_target_user_email(
        "somenewemail@email.com", creator, PerformanceFactory()
    )
    assert str(User.objects.get(email="somenewemail@email.com").id) == str(user.id)


@pytest.mark.django_db
def test_parse_target_user_email_without_permissions():
    creator = UserFactory(email="admin@email.com")
    with pytest.raises(AuthorizationException):
        parse_target_user_email("email@email.com", creator, PerformanceFactory())
    assert not User.objects.filter(email="somenewemail@email.com").exists()


@pytest.mark.django_db
def test_parse_target_user_email_without_target_email():
    creator = UserFactory(email="admin@email.com")
    user = parse_target_user_email(None, creator, PerformanceFactory())
    assert user.id == creator.id
