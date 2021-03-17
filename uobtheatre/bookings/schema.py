import itertools

import graphene
from graphene import relay
from graphene_django import DjangoListField, DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.bookings.models import Booking, ConcessionType, MiscCost, Ticket
from uobtheatre.productions.models import Performance
from uobtheatre.utils.exceptions import (
    AuthException,
    GQLFieldException,
    GQLNonFieldException,
    SafeMutation,
)
from uobtheatre.utils.schema import AuthRequiredMixin, FilterSet, IdInputField
from uobtheatre.venues.models import Seat, SeatGroup


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


class PriceBreakdownTicketNode(graphene.ObjectType):
    ticket_price = graphene.Int()
    number = graphene.Int()
    seat_group = graphene.Field("uobtheatre.venues.schema.SeatGroupNode")
    concession = graphene.Field("uobtheatre.bookings.schema.ConcessionTypeNode")
    total_price = graphene.Int()

    def resolve_total_price(self, info):
        return self.ticket_price * self.number


class PriceBreakdownNode(DjangoObjectType):
    tickets = graphene.List(PriceBreakdownTicketNode)
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
    payments = DjangoFilterConnectionField("uobtheatre.payments.schema.PaymentNode")

    def resolve_price_breakdown(self, info):
        return self

    class Meta:
        model = Booking
        filterset_class = BookingFilter
        interfaces = (relay.Node,)


class CreateTicketInput(graphene.InputObjectType):
    seat_group_id = IdInputField(required=True)
    concession_type_id = IdInputField(required=True)

    def to_ticket(self):
        return Ticket(
            seat_group=SeatGroup.objects.get(id=self.seat_group_id),
            concession_type=ConcessionType.objects.get(id=self.concession_type_id),
        )


class UpdateTicketInput(graphene.InputObjectType):
    seat_group_id = IdInputField(required=True)
    concession_type_id = IdInputField(required=True)
    seat_id = IdInputField(required=False)
    id = IdInputField(required=False)

    def to_ticket(self):

        if self.id is not None:
            return Ticket.objects.get(id=self.id)
        else:
            return Ticket(
                seat_group=SeatGroup.objects.get(id=self.seat_group_id),
                concession_type=ConcessionType.objects.get(id=self.concession_type_id),
                seat=Seat.objects.get(id=self.seat_id)
                if self.seat_id is not None
                else None,
            )


class CreateBooking(AuthRequiredMixin, SafeMutation):
    booking = graphene.Field(BookingNode)

    class Arguments:
        performance_id = IdInputField()
        tickets = graphene.List(CreateTicketInput, required=False)

    @classmethod
    def resolve_mutation(self, root, info, performance_id, tickets=[]):
        # Get the performance and if it doesn't exist throw an error
        performance = Performance.objects.get(id=performance_id)

        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))

        # Check the capacity of the show and its seat_groups
        err = performance.check_capacity(ticket_objects)
        if err:
            raise GQLNonFieldException(message=err, code=400)

        # If draft booking(s) already exists remove the bookings
        Booking.objects.filter(
            status=Booking.BookingStatus.IN_PROGRESS, performance_id=performance_id
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


class UpdateBooking(AuthRequiredMixin, SafeMutation):
    booking = graphene.Field(BookingNode)

    class Arguments:
        booking_id = IdInputField()
        tickets = graphene.List(UpdateTicketInput, required=False)

    @classmethod
    def resolve_mutation(self, root, info, booking_id, tickets=[]):
        booking = Booking.objects.get(id=booking_id, user=info.context.user)

        # Conert the given tickets to ticket objects
        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))

        addTickets, deleteTickets = booking.get_ticket_diff(ticket_objects)
        # Check the capacity of the show and its seat_groups
        err = booking.performance.check_capacity(ticket_objects)
        if err:
            raise GQLNonFieldException(message=err, code=400)

        # Save all the validated tickets
        for ticket in addTickets:
            ticket.booking = booking
            ticket.save()

        for ticket in deleteTickets:
            ticket.delete()

        return UpdateBooking(booking=booking)


class PayBooking(AuthRequiredMixin, SafeMutation):
    booking = graphene.Field(BookingNode)
    payment = graphene.Field("uobtheatre.payments.schema.PaymentNode")

    class Arguments:
        booking_id = IdInputField(required=True)
        price = graphene.Int(required=True)
        nonce = graphene.String(required=True)

    @classmethod
    def resolve_mutation(self, root, info, booking_id, price, nonce):
        # Get the performance and if it doesn't exist throw an error
        booking = Booking.objects.get(id=booking_id)

        if booking.total() != price:
            raise GQLNonFieldException(
                message="The booking price does not match the expected price"
            )

        if booking.status != Booking.BookingStatus.IN_PROGRESS:
            raise GQLNonFieldException(message="The booking is not in progress")

        payment = booking.pay(nonce)
        return PayBooking(booking=booking, payment=payment)


class Mutation(graphene.ObjectType):
    create_booking = CreateBooking.Field()
    update_booking = UpdateBooking.Field()
    pay_booking = PayBooking.Field()
