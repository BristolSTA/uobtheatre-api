import itertools

import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.bookings.models import Booking, ConcessionType, MiscCost
from uobtheatre.venues.schema import SeatGroupNode


class ConcessionTypeNode(DjangoObjectType):
    class Meta:
        model = ConcessionType
        interfaces = (relay.Node,)


class MiscCostNode(DjangoObjectType):
    class Meta:
        model = MiscCost
        interfaces = (relay.Node,)


class TicketNode(graphene.ObjectType):
    ticket_price = graphene.Int()
    number = graphene.Int()
    seat_group = graphene.Field(SeatGroupNode)
    concession = graphene.Field(ConcessionTypeNode)
    total_price = graphene.Int()

    def resolve_total_price(self, info):
        return self.ticket_price * self.number


class PriceBreakdownNode(DjangoObjectType):
    tickets = graphene.List(TicketNode)
    tickets_price = graphene.Int()
    discounts_value = graphene.Int()
    misc_costs = graphene.List(MiscCostNode)
    subtotal_price = graphene.Int()
    misc_costs_value = graphene.Int()
    total_price = graphene.Int()

    def resolve_tickets_price(self, info):
        return self.tickets_price()

    def resolve_discounts_value(self, info):
        return self.discount_value()

    def resolve_subtotal_price(self, info):
        return self.subtotal()

    def resolve_misc_costs_value(self, info):
        return self.misc_costs_value()

    def resolve_total_price(self, info):
        return self.total()

    def resolve_tickets(self, info):

        # Group the ticket together, this returns a list of tuples.
        # The first element of the tuple is itself a tuple which contains the
        # seat_group and concession_type, the second element of the typle
        # contains a list of all the elements in that group.
        groups = itertools.groupby(
            self.tickets.order_by("pk"),
            lambda ticket: (ticket.seat_group, ticket.concession_type),
        )

        return [
            TicketNode(
                ticket_price=self.performance.price_with_concession(
                    ticket_group[1],
                    self.performance.performance_seat_groups.get(
                        seat_group=ticket_group[0]
                    ).price
                    or 0,
                ),
                number=len(list(group)),
                seat_group=ticket_group[0],
                concession=ticket_group[1],
            )
            for ticket_group, group in groups
        ]

    def resolve_misc_costs(self, info):
        return [
            MiscCostNode(
                value=misc_cost.value(self),
            )
            for misc_cost in MiscCost.objects.all()
        ]

    class Meta:
        model = Booking
        interfaces = (relay.Node,)
        fields = (
            "tickets_price",
            "discounts_value",
            "subtotal_price",
            "misc_costs_value",
            "total_price",
        )


class BookingNode(DjangoObjectType):
    price_breakdown = graphene.Field(PriceBreakdownNode)

    def resolve_price_breakdown(self, info):
        return self

    class Meta:
        model = Booking
        interfaces = (relay.Node,)
        filter_fields = {
            "id": ("exact",),
            "booking_reference": ("exact",),
        }


class Query(graphene.ObjectType):
    bookings = DjangoFilterConnectionField(BookingNode)

    def resolve_bookings(self, info):
        # If the user is not authenticated then return none
        if not info.context.user.is_authenticated:
            return Booking.objects.none()
        # Otherwise return only the user's bookings
        return Booking.objects.filter(user=info.context.user)
