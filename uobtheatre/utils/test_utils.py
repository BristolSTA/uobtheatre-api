from uobtheatre.bookings.models import Ticket


def ticketDictListDictGen(ticketDictList):
    ticketObjectList = [Ticket(**ticketDict) for ticketDict in ticketDictList]
    return ticketListDictGen(ticketObjectList)


def ticketListDictGen(ticketList):
    ticketDict = {}
    for ticket in ticketList:
        ticketKey = (ticket.seat_group.id, ticket.concession_type.id, ticket.seat.id)
        if ticketKey in ticketDict:
            ticketDict[ticketKey] += 1
        else:
            ticketDict[ticketKey] = 1
    return ticketDict
