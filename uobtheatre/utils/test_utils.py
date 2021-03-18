def ticketDictListDictGen(ticketDictList):
    ticketDict = {}
    for ticket in ticketDictList:
        ticketKey = (
            ticket.get("seat_group_id"),
            ticket.get("concession_type_id"),
            ticket.get("seat_id"),
        )
        if ticketKey in ticketDict:
            ticketDict[ticketKey] += 1
        else:
            ticketDict[ticketKey] = 1
    return ticketDict


def ticketListDictGen(ticketList):
    ticketDict = {}
    for ticket in ticketList:
        ticketKey = (ticket.seat_group.id, ticket.concession_type.id, ticket.seat.id)
        if ticketKey in ticketDict:
            ticketDict[ticketKey] += 1
        else:
            ticketDict[ticketKey] = 1
    return ticketDict
