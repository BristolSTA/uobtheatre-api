import itertools

import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphql import GraphQLError

from uobtheatre.bookings.models import Booking, ConcessionType, MiscCost, Ticket
from uobtheatre.productions.models import Performance
from uobtheatre.utils.schema import IdInputField
from uobtheatre.venues.models import SeatGroup


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
    seat_group = graphene.Field("uobtheatre.venues.schema.SeatGroupNode")
    concession = graphene.Field("uobtheatre.bookings.schema.ConcessionTypeNode")
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


class CreateTicketInput(graphene.InputObjectType):
    # seat_group_id = graphene.String(required=True)
    seat_group_id = IdInputField(required=True)
    concession_type_id = IdInputField(required=True)

    def to_ticket(self):
        return Ticket(
            seat_group=SeatGroup.objects.get(id=self.seat_group_id),
            concession_type=ConcessionType.objects.get(id=self.concession_type_id),
        )


class CreateBooking(graphene.Mutation):
    booking = graphene.Field(BookingNode)

    class Arguments:
        performance_id = IdInputField()
        tickets = graphene.List(CreateTicketInput, required=False)

    @classmethod
    def mutate(self, root, info, performance_id, tickets):
        if not info.context.user.is_authenticated:
            raise GraphQLError("You must be logged in to create a booking")

        # Get the performance and if it doesn't exist throw an error
        # performance.to_obj()
        print("In the hting")
        print(performance_id)
        performance = Performance.objects.get(id=performance_id)
        print("Hello")

        # Covert the given tickets to ticket objects
        # If any of the gets throw an error (cant find the id) this will be handled by graphene
        # e.g. "ConcessionType matching query does not exist."
        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))

        # Check the capacity of the show and its seat_groups
        err = performance.check_capacity(ticket_objects)
        if err:
            raise GraphQLError(err)

        # If draft booking(s) already exists remove the bookings
        Booking.objects.filter(
            status=Booking.BookingStatus.INPROGRESS, performance_id=performance_id
        ).delete()

        # Create the booking
        booking = Booking.objects.create(
            user=info.context.user, performance=performance
        )

        # Save all the validated tickets
        for ticket in ticket_objects:
            ticket.booking = booking
            ticket.save()

        return CreateBooking(booking=booking)


class Query(graphene.ObjectType):
    bookings = DjangoFilterConnectionField(BookingNode)

    def resolve_bookings(self, info):
        # If the user is not authenticated then return none
        if not info.context.user.is_authenticated:
            return Booking.objects.none()
        # Otherwise return only the user's bookings
        return Booking.objects.filter(user=info.context.user)


class Mutation(graphene.ObjectType):
    # booking = BookingMutation.Field()
    create_booking = CreateBooking.Field()
