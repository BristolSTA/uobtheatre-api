import itertools
from typing import List

import graphene
from django.db.models import Count
from django_filters import OrderingFilter
from graphene import relay
from graphene_django import DjangoListField, DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphql_auth.schema import UserNode

from uobtheatre.bookings.models import (
    Booking,
    ConcessionType,
    Discount,
    DiscountRequirement,
    MiscCost,
    Ticket,
)
from uobtheatre.productions.models import Performance
from uobtheatre.utils.enums import GrapheneEnumMixin
from uobtheatre.utils.exceptions import (
    GQLExceptions,
    GQLFieldException,
    GQLNonFieldException,
    SafeMutation,
)
from uobtheatre.utils.filters import FilterSet
from uobtheatre.utils.schema import AuthRequiredMixin, IdInputField
from uobtheatre.venues.models import Seat, SeatGroup


class ConcessionTypeNode(DjangoObjectType):
    class Meta:
        model = ConcessionType
        interfaces = (relay.Node,)
        exclude = ("discountrequirement_set",)


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

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.annotate(
            number_of_tickets_required=Count("requirements__number")
        ).filter(number_of_tickets_required__gt=1)

    class Meta:
        model = Discount
        interfaces = (relay.Node,)


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
                    ),
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
    """Custom filter for BookingNode.

    Restricts BookingNode to only return Bookings owned by the User. Adds
    ordering filter for created_at.
    """

    class Meta:
        model = Booking
        fields = "__all__"

    # NOTE: When we add back in Bookings endpoint only admin users should be
    # able to get all bookings otherwise we should return only user bookings.
    # Booings can be accessed from a performance, if this was not here then the
    # users would be able all peoples bookings.
    @property
    def qs(self):
        """Restrict the queryset to only return user bookings.

        Returns:
            Queryset: Booking queryset, filter with only user's bookings.

        """
        if self.request.user.is_authenticated:
            return super().qs.filter(user=self.request.user)
        return Booking.objects.none()

    order_by = OrderingFilter(fields=("created_at",))


BookingStatusSchema = graphene.Enum.from_enum(Booking.BookingStatus)


class BookingNode(GrapheneEnumMixin, DjangoObjectType):
    price_breakdown = graphene.Field(PriceBreakdownNode)
    tickets = DjangoListField(TicketNode)
    user = graphene.Field(UserNode)
    payments = DjangoFilterConnectionField("uobtheatre.payments.schema.PaymentNode")

    def resolve_payments(self, info):
        return self.payments.all()

    def resolve_price_breakdown(self, info):
        return self

    class Meta:
        model = Booking
        filterset_class = BookingFilter
        interfaces = (relay.Node,)


class CreateTicketInput(graphene.InputObjectType):
    """Input for creating Tickets with mutations."""

    seat_group_id = IdInputField(required=True)
    concession_type_id = IdInputField(required=True)

    def to_ticket(self):
        """Get Ticket object from input.

        This creates a Ticket object based on the inputs to the mutation.

        Note:
            This is a Ticket object but has not yet been saved to the database.

        Returns:
            Ticket: The ticket to be created.
        """
        return Ticket(
            seat_group=SeatGroup.objects.get(id=self.seat_group_id),
            concession_type=ConcessionType.objects.get(id=self.concession_type_id),
        )


class UpdateTicketInput(graphene.InputObjectType):
    """Input to update existing Tickets or create new ones with a mutation."""

    seat_group_id = IdInputField(required=True)
    concession_type_id = IdInputField(required=True)
    seat_id = IdInputField(required=False)
    id = IdInputField(required=False)

    def to_ticket(self):
        """Returns the Ticket object to be updated/created.

        If a Ticket already exists it is the exisitng Ticket object (saved in
        the database). If not a new Ticket object is created (and not yet saved
        to the database).

        Returns:
            Ticket: The ticket to be updated/created.
        """

        if self.id is not None:
            return Ticket.objects.get(id=self.id)
        return Ticket(
            seat_group=SeatGroup.objects.get(id=self.seat_group_id),
            concession_type=ConcessionType.objects.get(id=self.concession_type_id),
            seat=Seat.objects.get(id=self.seat_id)
            if self.seat_id is not None
            else None,
        )


class TicketIDInput(graphene.InputObjectType):
    ticket_id = IdInputField(required=True)

    def to_ticket(self):
        return Ticket.objects.get(id=self.ticket_id)


class CreateBooking(AuthRequiredMixin, SafeMutation):
    """Mutation to create a Booking"""

    booking = graphene.Field(BookingNode)

    class Arguments:
        performance_id = IdInputField()
        tickets = graphene.List(CreateTicketInput, required=False)

    @classmethod
    def resolve_mutation(
        cls, _, info, performance_id: int, tickets: List[CreateTicketInput] = None
    ):

        if tickets is None:
            tickets = []

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
    """Mutation to updated an existing Booking

    Args:
        booking_id (str): Global id of booking which is being updated
        tickets (Ticket): The new set tickets which the booking should contain
            after the update. If an empty list is provided all the bookings
            tickets will be deleted. If no list is provided the bookings
            tickets will not be changed.
    """

    booking = graphene.Field(BookingNode)

    class Arguments:
        booking_id = IdInputField()
        tickets = graphene.List(UpdateTicketInput, required=False)

    @classmethod
    def resolve_mutation(cls, _, info, booking_id, tickets=None):

        booking = Booking.objects.get(id=booking_id, user=info.context.user)

        # If no tickets are provided then we will not update the bookings
        # tickets.
        if tickets is None:
            return UpdateBooking(booking=booking)

        # Convert the given tickets to ticket objects
        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))

        add_tickets, delete_tickets = booking.get_ticket_diff(ticket_objects)
        # Check the capacity of the show and its seat_groups
        err = booking.performance.check_capacity(ticket_objects)
        if err:
            raise GQLNonFieldException(message=err, code=400)

        # Save all the validated tickets
        for ticket in add_tickets:
            ticket.booking = booking
            ticket.save()

        for ticket in delete_tickets:
            ticket.delete()

        return UpdateBooking(booking=booking)


class PayBooking(AuthRequiredMixin, SafeMutation):
    """Mutation to pay for a Booking.

    Args:
        booking_id (str): The gloabl id of the Booking being paid for.
        price (int): The expected price of the Booking. This must match the
            actual price of the Booking. This is used to ensure the front end
            is showing the true price which will be paid.
        nonce (str): The Square payment form nonce.

    Returns:
        booking (BookingNode): The Booking which was paid for.
        payment (PaymentNode): The Payment which was created by the
            transaction.

    Raises:
        GQLNonFieldException: If the Payment was unsucessful.
    """

    booking = graphene.Field(BookingNode)
    payment = graphene.Field("uobtheatre.payments.schema.PaymentNode")

    class Arguments:
        booking_id = IdInputField(required=True)
        price = graphene.Int(required=True)
        nonce = graphene.String(required=True)

    @classmethod
    def resolve_mutation(cls, _, info, booking_id, price, nonce):
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


class CheckInBooking(AuthRequiredMixin, SafeMutation):
    """Mutation to check in the tickets of a Booking.

    Args:
        booking_reference (str): The booking reference.
        performance_id (str): The id of the performance that the ticket is
            being booked in for, this should match the performance of the
            booking. If this is not the case an error will be thrown as the
            Booking cannot be used for the Performance.


    Returns:
        booking (BookingNode): The Booking which was paid for.
        performance (PaymentNode): The Performance.

    Raises:
        GQLNonFieldException: If at least one ticket check in was unsuccessful
    """

    performance = graphene.Field("uobtheatre.productions.schema.PerformanceNode")
    booking = graphene.Field(BookingNode)

    class Arguments:
        booking_reference = graphene.String(required=True)
        performance_id = IdInputField(required=True)
        tickets = graphene.List(TicketIDInput, required=True)

    @classmethod
    def resolve_mutation(cls, _, info, booking_reference, tickets, performance_id):
        performance = Performance.objects.get(id=performance_id)
        booking = Booking.objects.get(reference=booking_reference)

        # check if the booking pertains to the correct performance
        if booking.performance != performance:
            raise GQLFieldException(
                field="performance_id",
                message="The booking performance does not match the given performance.",
            )
            # raise booking performance does not match performance given

        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))

        tickets_not_in_booking = [
            ticket for ticket in ticket_objects if ticket.booking != booking
        ]

        if tickets_not_in_booking:
            raise GQLExceptions(
                exceptions=[
                    GQLFieldException(
                        field="booking_reference",
                        message=f"The ticket booking of ticket {ticket.id} does not match the given booking.",
                    )
                    for ticket in tickets_not_in_booking
                ]
            )

        tickets_checked_in = [ticket for ticket in ticket_objects if ticket.checked_in]

        if tickets_checked_in:
            raise GQLExceptions(
                exceptions=[
                    GQLNonFieldException(
                        message=f"Ticket {ticket.id} is already checked in"
                    )
                    for ticket in tickets_checked_in
                ]
            )

        for ticket in ticket_objects:
            ticket.check_in()

        return CheckInBooking(booking=booking, performance=performance)


class UnCheckInBooking(AuthRequiredMixin, SafeMutation):
    """Mutation to un-check in the tickets of a Booking.

    Args:
        booking_reference (str): The booking reference
        performance_id (str): The id of the performance that the ticket is
            being booked in for, this should match the performance of the
            booking. If this is not the case an error will be thrown as the
            Booking cannot be used for the Performance.


    Returns:
        booking (BookingNode): The Booking.
        performance (PaymentNode): The Performance.

    Raises:
        GQLNonFieldException: If the un-check in was unsuccessful
    """

    performance = graphene.Field("uobtheatre.productions.schema.PerformanceNode")
    booking = graphene.Field(BookingNode)

    class Arguments:
        booking_reference = graphene.String(required=True)
        performance_id = IdInputField(required=True)
        tickets = graphene.List(TicketIDInput, required=True)

    @classmethod
    def resolve_mutation(cls, _, info, booking_reference, tickets, performance_id):
        performance = Performance.objects.get(id=performance_id)
        booking = Booking.objects.get(reference=booking_reference)

        # check if the booking pertains to the correct performance
        if booking.performance != performance:
            raise GQLFieldException(
                field="performance_id",
                message="The booking performance does not match the given performance.",
            )
            # raise booking performance does not match performance given

        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))
        # loop through the ticket IDs given

        tickets_not_in_booking = [
            ticket for ticket in ticket_objects if ticket.booking != booking
        ]

        if tickets_not_in_booking:
            raise GQLExceptions(
                exceptions=[
                    GQLFieldException(
                        field="booking_reference",
                        message=f"The ticket booking of ticket {ticket.id} does not match the given booking.",
                    )
                    for ticket in tickets_not_in_booking
                ]
            )

        for ticket in ticket_objects:
            ticket.uncheck_in()

        return UnCheckInBooking(booking=booking, performance=performance)


class Mutation(graphene.ObjectType):
    create_booking = CreateBooking.Field()
    update_booking = UpdateBooking.Field()
    pay_booking = PayBooking.Field()
    check_in_booking = CheckInBooking.Field()
    uncheck_in_booking = UnCheckInBooking.Field()
