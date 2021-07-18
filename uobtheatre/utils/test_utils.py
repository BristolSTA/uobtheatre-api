"""
Utils for the tests
"""

import pytest

from uobtheatre.bookings.models import Ticket
from uobtheatre.utils.utils import combinations


@pytest.mark.parametrize(
    "inputs, length, output",
    [
        (
            [1, 2, 3],
            2,
            [
                (1,),
                (2,),
                (3,),
                (1, 1),
                (1, 2),
                (1, 3),
                (2, 1),
                (2, 2),
                (2, 3),
                (3, 1),
                (3, 2),
                (3, 3),
            ],
        ),
        (
            [1, 2, 3],
            3,
            [
                (1,),
                (2,),
                (3,),
                (1, 1),
                (1, 2),
                (1, 3),
                (2, 1),
                (2, 2),
                (2, 3),
                (3, 1),
                (3, 2),
                (3, 3),
                (1, 1, 1),
                (1, 1, 2),
                (1, 1, 3),
                (1, 2, 1),
                (1, 2, 2),
                (1, 2, 3),
                (1, 3, 1),
                (1, 3, 2),
                (1, 3, 3),
                (2, 1, 1),
                (2, 1, 2),
                (2, 1, 3),
                (2, 2, 1),
                (2, 2, 2),
                (2, 2, 3),
                (2, 3, 1),
                (2, 3, 2),
                (2, 3, 3),
                (3, 1, 1),
                (3, 1, 2),
                (3, 1, 3),
                (3, 2, 1),
                (3, 2, 2),
                (3, 2, 3),
                (3, 3, 1),
                (3, 3, 2),
                (3, 3, 3),
            ],
        ),
    ],
)
def test_combinations(inputs, length, output):
    calculated_combinations = combinations(inputs, length)
    assert set(calculated_combinations) == set(output)
    assert len(calculated_combinations) == len(output)


def ticket_list_dict_gen(ticket_list):
    """
    Given a lits of Ticket objects, return a dictionary with the count of each ticket.
    """
    ticket_dict = {}
    for ticket in ticket_list:
        ticket_key = (ticket.seat_group.id, ticket.concession_type.id, ticket.seat.id)
        if ticket_key in ticket_dict:
            ticket_dict[ticket_key] += 1
        else:
            ticket_dict[ticket_key] = 1
    return ticket_dict


def ticket_dict_list_dict_gen(ticket_dict_list):
    """
    Given a lits of ticket dictionaries, return a dictionary with the count of each ticket.
    """
    ticket_object_list = [Ticket(**ticketDict) for ticketDict in ticket_dict_list]
    return ticket_list_dict_gen(ticket_object_list)
