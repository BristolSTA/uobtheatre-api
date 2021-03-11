import itertools

import graphene
from graphene import relay
from graphene_django import DjangoListField, DjangoObjectType
from graphql_auth.schema import UserNode

from uobtheatre.bookings.models import (
    Booking,
    ConcessionType,
    Discount,
    DiscountRequirement,
    MiscCost,
    Ticket,
)
from uobtheatre.utils.schema import FilterSet


class ConcessionTypeNode(DjangoObjectType):
    class Meta:
        model = ConcessionType
        interfaces = (relay.Node,)


class MiscCostNode(DjangoObjectType):
    class Meta:
        model = MiscCost
        interfaces = (relay.Node,)


class TicketNode(DjangoObjectType):
    class Meta:
        model = Ticket
        interfaces = (relay.Node,)


class DiscountRequirementNode(DjangoObjectType):
    class Meta:
        model = DiscountRequirement
        interfaces = (relay.Node,)


class DiscountNode(DjangoObjectType):
    requirements = DjangoListField(DiscountRequirementNode)

    class Meta:
        model = Discount
        interfaces = (relay.Node,)


class DiscountNodeMixin:
    discounts = DjangoListField(DiscountNode)

    def resolve_discounts(self, info):
        return [
            discount
            for discount in self.discounts.all()
            if not discount.is_single_discount()
        ]


class PriceBreakdownTicketNode(graphene.ObjectType):
    ticket_price = graphene.Int(required=True)
    number = graphene.Int(required=True)
    seat_group = graphene.Field("uobtheatre.venues.schema.SeatGroupNode")
    concession_type = graphene.Field("uobtheatre.bookings.schema.ConcessionTypeNode")
    total_price = graphene.Int(required=True)

    def resolve_total_price(self, info):
        return self.ticket_price * self.number


class PriceBreakdownNode(DjangoObjectType):
    tickets = graphene.List(PriceBreakdownTicketNode)
    tickets_price = graphene.Int(required=True)
    discounts_value = graphene.Int(required=True)
    misc_costs = graphene.List(MiscCostNode)
    subtotal_price = graphene.Int(required=True)
    misc_costs_value = graphene.Int(required=True)
    total_price = graphene.Int(required=True)
    tickets_discounted_price = graphene.Int(required=True)

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

    def resolve_tickets_discounted_price(self, info):
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
            PriceBreakdownTicketNode(
                ticket_price=self.performance.price_with_concession(
                    ticket_group[1],
                    self.performance.performance_seat_groups.get(
                        seat_group=ticket_group[0]
                    ).price
                    or 0,
                ),
                number=len(list(group)),
                seat_group=ticket_group[0],
                concession_type=ticket_group[1],
            )
            for ticket_group, group in groups
        ]

    def resolve_misc_costs(self, info):
        # For some reason the node isnt working for ive had to add all the
        # values in here.
        return [
            MiscCostNode(
                misc_cost,
                name=misc_cost.name,
                description=misc_cost.description,
                value=misc_cost.get_value(self),
                percentage=misc_cost.percentage,
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


class BookingFilter(FilterSet):
    class Meta:
        model = Booking
        fields = "__all__"

    # TODO When we add back in Bookings endpoint only admin users should be
    # able to get all bookings otherwise we should return only user bookings.
    @property
    def qs(self):
        # Restrict the filterset to only return user bookings
        if self.request.user.is_authenticated:
            return super(BookingFilter, self).qs.filter(user=self.request.user)
        else:
            return Booking.objects.none()


BookingStatusSchema = graphene.Enum.from_enum(Booking.BookingStatus)


class BookingNode(DjangoObjectType):
    price_breakdown = graphene.Field(PriceBreakdownNode)
    tickets = DjangoListField(TicketNode)
    user = graphene.Field(UserNode)

    def resolve_price_breakdown(self, info):
        return self

    class Meta:
        model = Booking
        filterset_class = BookingFilter
        interfaces = (relay.Node,)
