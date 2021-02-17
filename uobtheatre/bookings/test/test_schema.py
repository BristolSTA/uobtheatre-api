import pytest

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
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_bookings_schema(gql_client_flexible, gql_id):

    booking = BookingFactory(status=Booking.BookingStatus.INPROGRESS)
    # Create a booking that is not owned by the same user
    BookingFactory(status=Booking.BookingStatus.INPROGRESS)
    tickets = [TicketFactory(booking=booking) for _ in range(10)]

    request_query = """
        {
          authUser {
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
    assert response == {"data": {"authUser": None}}

    # When we are logged in expect only the user's bookings
    client.set_user(booking.user)
    response = client.execute(request_query)
    assert response == {
        "data": {
            "authUser": {
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
          authUser {
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

    response_booking_price_break_down = response["data"]["authUser"]["bookings"][
        "edges"
    ][0]["node"]["priceBreakdown"]
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
      authUser {
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
            "authUser": {
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
