from typing import List, Optional

import graphene
from graphene.types.scalars import Float

from uobtheatre.bookings.models import Booking, Ticket, max_tickets_per_booking
from uobtheatre.bookings.schema import BookingNode
from uobtheatre.discounts.models import ConcessionType
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.transaction_providers import (
    Card,
    Cash,
    SquareOnline,
    SquarePOS,
)
from uobtheatre.productions.abilities import BookForPerformance
from uobtheatre.productions.models import Performance, Production
from uobtheatre.users.models import User
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    GQLException,
    GQLExceptions,
    SafeMutation,
)
from uobtheatre.utils.schema import AuthRequiredMixin, IdInputField
from uobtheatre.utils.validators import PercentageValidator
from uobtheatre.venues.models import Seat, SeatGroup


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


def parse_target_user_email(
    target_user_email: Optional[str], creator_user: User, performance: Performance
) -> User:
    """Parse provided user email to user and check permissions.

    Given an email of a user return that email. If the email is not provided
    return the creator. If the email is provided but the user does not have
    permission to create a booking for another user, throw and error.

    Args:
        target_user_email: The email of the user that the booking is being
            given to.
        creator_user: The user creating/updating the booking.
        performance: The performance that the booking if for.

    Returns:
        User: The user which the booking is being created for. (This may be the
            same as the creator if not target_user_email is provided.)

    Raises:
        AuthorizationException: If the user does not have permission to create a
            booking.
    """
    # Only (box office) admins can create a booking for a different user
    if target_user_email and not creator_user.has_perm(
        "productions.boxoffice", performance.production
    ):
        raise AuthorizationException(
            message="You do not have permission to create a booking for another user.",
            field="target_user_email",
        )

    # If a target user is provided get that user, if not then this booking is intended for the user that is logged in
    if target_user_email:
        target_user, _ = User.objects.get_or_create(
            email=target_user_email,
            defaults={"first_name": "Anonymous", "last_name": "User"},
        )
        return target_user
    return creator_user


def parse_admin_discount_percentage(
    admin_discount_percentage: Float, user: User, production: Production
):
    """Parse provided admin discount and check permissions.
    Args:
        admin_discount_percentage: The decimal percentage discount (e.g. 0.2 = 20%)
        user: The user creating/updating the booking.
        production: The production that the booking is for.

    Returns:
        Float: The parsed/verified float

    Raises:
        AuthorizationException: If the user does not have permission to change the admin discount
        GQLException: If the admin discount percentage is invalid
    """
    if not user.has_perm("change_production", production):
        raise AuthorizationException(
            message="You do not have permission to assign an admin discount",
            field="admin_discount_percentage",
        )
    validator = PercentageValidator("admin_discount_percentage")
    validator(admin_discount_percentage)
    return admin_discount_percentage


def delete_user_drafts(user, performance_id, booking_id=None):
    """Remove's the users exisiting draft booking for the given performance"""
    bookings = user.bookings
    if booking_id:
        bookings = bookings.exclude(id=booking_id)
    bookings.filter(
        status=Payable.Status.IN_PROGRESS, performance_id=performance_id
    ).delete()


class CreateBooking(AuthRequiredMixin, SafeMutation):
    """Mutation to create a Booking

    Args:
        performance_id (str): Global id of performance which the booking is
            being created for.
        tickets (Ticket): The tickets which should be created for the booking.
        target_user_email (str): The email of the user that this booking is
            being created for. (Optional)
    """

    booking = graphene.Field(BookingNode)

    class Arguments:
        performance_id = IdInputField()
        tickets = graphene.List(CreateTicketInput, required=False)
        target_user_email = graphene.String(required=False)  # User email
        admin_discount_percentage = graphene.Float()

    @classmethod
    def resolve_mutation(
        cls,
        _,
        info,
        performance_id: int,
        tickets: List[CreateTicketInput] = None,
        target_user_email: str = None,
        admin_discount_percentage: float = None,
    ):

        if tickets is None:
            tickets = []

        # Get the performance and if it doesn't exist throw an error
        performance = Performance.objects.get(id=performance_id)

        if len(tickets) > max_tickets_per_booking() and not info.context.user.has_perm(
            "boxoffice", performance.production
        ):
            raise GQLException(
                message="You may only book a maximum of %s tickets"
                % max_tickets_per_booking(),
                code=422,
            )

        # Check performance is bookable
        if not BookForPerformance.user_has_for(info.context.user, performance):
            raise GQLException(
                message="This performance is not able to be booked at the moment"
            )

        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))

        # Check the capacity of the show and its seat_groups
        performance.check_capacity(ticket_objects)

        user = parse_target_user_email(
            target_user_email, info.context.user, performance
        )

        delete_user_drafts(user, performance_id)

        # Create the booking
        extra_args = {}
        if admin_discount_percentage:
            extra_args["admin_discount_percentage"] = parse_admin_discount_percentage(
                admin_discount_percentage, info.context.user, performance.production
            )

        booking = Booking.objects.create(
            user=user, creator=info.context.user, performance=performance, **extra_args
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
        target_user_email (str): The email of the user that this booking is
            being created for. (Optional)
    """

    booking = graphene.Field(BookingNode)

    class Arguments:
        booking_id = IdInputField()
        tickets = graphene.List(UpdateTicketInput, required=False)
        target_user_email = graphene.String(required=False)  # User email
        admin_discount_percentage = graphene.Float()

    @classmethod
    def resolve_mutation(
        cls,
        _,
        info,
        booking_id: int,
        tickets: List[CreateTicketInput] = None,
        target_user_email: str = None,
        admin_discount_percentage: Float = None,
    ):

        booking = Booking.objects.get(id=booking_id)

        # Can only edit this booking if belongs to the user, or is box office
        if booking.user.id != info.context.user.id and not info.context.user.has_perm(
            "productions.boxoffice", booking.performance.production
        ):
            raise AuthorizationException(
                message="You do not have permission to access this booking.",
            )

        # Booking must be in progress to update
        if booking.status != Payable.Status.IN_PROGRESS:
            raise GQLException(
                message="This booking is not in progress, and so cannot be edited"
            )

        # Booking must not be expired
        if booking.is_reservation_expired:
            raise GQLException(
                message="This booking has expired. Please create a new booking."
            )

        if admin_discount_percentage:
            booking.admin_discount_percentage = parse_admin_discount_percentage(
                admin_discount_percentage,
                info.context.user,
                booking.performance.production,
            )
            booking.save()

        if target_user_email:
            user = parse_target_user_email(
                target_user_email, info.context.user, booking.performance
            )
            delete_user_drafts(user, booking.performance_id, booking.id)
            booking.user = user
            booking.save()

        # If no tickets are provided then we will not update the bookings
        # tickets.
        if tickets is None:
            return UpdateBooking(booking=booking)

        # Convert the given tickets to ticket objects
        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))
        add_tickets, delete_tickets, total_number_of_tickets = booking.get_ticket_diff(
            ticket_objects
        )

        if (
            total_number_of_tickets > max_tickets_per_booking()
            and not info.context.user.has_perm(
                "boxoffice", booking.performance.production
            )
        ):
            raise GQLException(
                message="You may only book a maximum of %s tickets"
                % max_tickets_per_booking(),
                code=422,
            )

        # Check the capacity of the show and its seat_groups
        booking.performance.check_capacity(ticket_objects)

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
        payment_provider (PaymentProvider): The provider used for the payment.

    Returns:
        booking (BookingNode): The Booking which was paid for.
        transaction (TransactionNode): The Transaction which was created by the
            transaction.

    Raises:
        GQLException: If the Payment was unsucessful.
    """

    booking = graphene.Field(BookingNode)
    payment = graphene.Field("uobtheatre.payments.schema.TransactionNode")

    class Arguments:
        booking_id = IdInputField(required=True)
        price = graphene.Int(required=True)
        nonce = graphene.String(required=False)
        payment_provider = graphene.Argument(
            "uobtheatre.payments.schema.PaymentMethodsEnum"
        )
        device_id = graphene.String(required=False)
        idempotency_key = graphene.String(required=False)
        verify_token = graphene.String(required=False)

    @classmethod
    def resolve_mutation(  # pylint: disable=too-many-arguments, too-many-branches
        cls,
        _,
        info,
        booking_id,
        price,
        nonce=None,
        payment_provider=SquareOnline.name,
        device_id=None,
        idempotency_key=None,
        verify_token=None,
    ):

        # Get the performance and if it doesn't exist throw an error
        booking = Booking.objects.get(id=booking_id)

        # Verify user can access booking
        if booking.user.id != info.context.user.id and not info.context.user.has_perm(
            "productions.boxoffice", booking.performance.production
        ):
            raise AuthorizationException(
                message="You do not have permission to access this booking.",
            )

        # Booking must not be paid for already
        if not booking.status == Payable.Status.IN_PROGRESS:
            raise GQLException(
                message=f"This booking can't be paid for ({booking.get_status_display()})"
            )

        # Check if booking hasn't expired
        if booking.is_reservation_expired:
            raise GQLException(
                message="This booking has expired. Please create a new booking."
            )

        # Verify user can use payment provider
        if not (
            payment_provider == SquareOnline.name
        ) and not info.context.user.has_perm(
            "productions.boxoffice", booking.performance.production
        ):
            raise AuthorizationException(
                message=f"You do not have permission to pay for a booking with the {payment_provider} provider.",
                field="payment_provider",
            )

        if booking.total != price:
            raise GQLException(
                message="The booking price does not match the expected price"
            )

        # Booking must have at least one ticket
        if booking.tickets.count() == 0:
            raise GQLException(message="The booking must have at least one ticket")

        # If the booking is free, we don't care about the payment provider. Otherwise, we do
        if booking.total == 0:
            booking.complete()
            return PayBooking(booking=booking)

        if not idempotency_key and payment_provider in [
            SquareOnline.name,
            SquarePOS.name,
        ]:
            raise GQLException(
                message=f"An idempotency key is required when using {payment_provider} provider.",
                field="idempotency_key",
                code="missing_required",
            )

        if payment_provider == SquareOnline.name:
            if not nonce:
                raise GQLException(
                    message=f"A nonce is required when using {payment_provider} provider.",
                    field="nonce",
                    code="missing_required",
                )
            payment_method = SquareOnline(nonce, idempotency_key, verify_token)
        elif payment_provider == SquarePOS.name:
            if not device_id:
                raise GQLException(
                    message=f"A device_id is required when using {payment_provider} provider.",
                    field="device_id",
                    code="missing_required",
                )
            payment_method = SquarePOS(device_id, idempotency_key)
        elif payment_provider == Cash.name:
            payment_method = Cash()
        elif payment_provider == Card.name:
            payment_method = Card()
        else:
            raise GQLException(  # pragma: no cover
                message=f"Unsupported payment provider {payment_provider}."
            )

        transaction = booking.pay(payment_method)
        return PayBooking(booking=booking, payment=transaction)


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
        performance (PerformanceNode): The Performance.

    Raises:
        GQLException: If the booking does not match the performance booking
        GQLExceptions: If at least one ticket check in was unsuccessful
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
            raise GQLException(
                field="performance_id",
                message="The booking performance does not match the given performance.",
            )
            # raise booking performance does not match performance given

        # Check user has permission to check in this booking
        if not info.context.user.has_perm(
            "productions.boxoffice", performance.production
        ):
            raise AuthorizationException(
                message="You do not have permission to check in this booking.",
            )

        # Check the booking has been paid for
        if not booking.status == Payable.Status.PAID:
            raise GQLException(
                field="booking_reference",
                message=f"This booking has not been paid for (Status: {booking.get_status_display()})",
            )

        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))

        tickets_not_in_booking = [
            ticket for ticket in ticket_objects if ticket.booking != booking
        ]

        if tickets_not_in_booking:
            raise GQLExceptions(
                exceptions=[
                    GQLException(
                        field="booking_reference",
                        message=f"The booking of ticket {ticket.id} does not match the given booking.",
                    )
                    for ticket in tickets_not_in_booking
                ]
            )

        tickets_checked_in = [ticket for ticket in ticket_objects if ticket.checked_in]

        if tickets_checked_in:
            raise GQLExceptions(
                exceptions=[
                    GQLException(message=f"Ticket {ticket.id} is already checked in")
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
        performance (PerformanceNOde): The Performance.

    Raises:
        GQLException: If the un-check in was unsuccessful
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
            # raise booking performance does not match performance given
            raise GQLException(
                field="performance_id",
                message="The booking performance does not match the given performance.",
            )

        # Check user has permission to check in this booking
        if not info.context.user.has_perm(
            "productions.boxoffice", performance.production
        ):
            raise AuthorizationException(
                message="You do not have permission to uncheck in this booking.",
            )

        ticket_objects = list(map(lambda ticket: ticket.to_ticket(), tickets))
        # loop through the ticket IDs given

        tickets_not_in_booking = [
            ticket for ticket in ticket_objects if ticket.booking != booking
        ]

        if tickets_not_in_booking:
            raise GQLExceptions(
                exceptions=[
                    GQLException(
                        field="booking_reference",
                        message=f"The booking of ticket {ticket.id} does not match the given booking.",
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
