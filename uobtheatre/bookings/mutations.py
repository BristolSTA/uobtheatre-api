import graphene

from uobtheatre.bookings.abilities import ModifyBooking
from uobtheatre.bookings.exceptions import (
    BookingTransferCheckedInTicketsException,
    BookingTransferToDifferentProductionException,
)
from uobtheatre.bookings.forms import BookingForm
from uobtheatre.bookings.models import Booking, Ticket
from uobtheatre.bookings.schema import BookingNode
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.transaction_providers import (
    Card,
    Cash,
    SquareOnline,
    SquarePOS,
)
from uobtheatre.productions.abilities import BookForPerformance
from uobtheatre.productions.exceptions import NotBookableException
from uobtheatre.productions.models import Performance
from uobtheatre.users.abilities import AllwaysPasses
from uobtheatre.utils.exceptions import (
    AuthorizationException,
    GQLException,
    GQLExceptions,
    SafeMutation,
)
from uobtheatre.utils.schema import (
    AuthRequiredMixin,
    IdInputField,
    ModelDeletionMutation,
    SafeFormMutation,
)


class TicketIDInput(graphene.InputObjectType):
    ticket_id = IdInputField(required=True)

    def to_ticket(self):
        return Ticket.objects.get(id=self.ticket_id)


class BookingMutation(SafeFormMutation, AuthRequiredMixin):
    """Create/update mutation for booking objects"""

    booking = graphene.Field(BookingNode)

    @classmethod
    def authorize_request(cls, root, info, **inputs):
        super().authorize_request(root, info, **inputs)

        new_performance = cls.get_python_value(root, info, inputs, "performance")
        current_instance = cls.get_object_instance(root, info, **inputs)

        target_performance = new_performance or current_instance.performance

        # Authorize fields
        cls.authorize_performance(info, target_performance)
        cls.authorize_admin_discount(info, target_performance, **inputs)
        cls.authorize_target_user(info, target_performance, **inputs)

        # Authorize specifically for creation / update
        if not cls.is_creation(**inputs):
            cls.authorize_update(current_instance)

    @classmethod
    def authorize_update(cls, instance):
        """Authorize the update operation"""
        # Booking must not be expired
        if instance.is_reservation_expired:
            raise GQLException(
                message="This booking has expired. Please create a new booking."
            )

    @classmethod
    def authorize_target_user(cls, info, target_performance, **inputs):
        """Authorize the targer user (via email) parameter"""
        # Target user
        if ("user" in inputs or "user_email" in inputs) and (
            not info.context.user.has_perm(
                "productions.boxoffice", target_performance.production
            )
        ):
            raise AuthorizationException(
                "You do not have permission to create a booking for another user",
                field="user_email",
            )

    @classmethod
    def authorize_performance(cls, info, target_performance):
        """Authorize the performance given"""
        # Check performance is bookable
        if not BookForPerformance.user_has_for(info.context.user, target_performance):
            raise NotBookableException(
                message="This performance is not able to be booked at the moment"
            )

    @classmethod
    def authorize_admin_discount(cls, info, target_performance, **inputs):
        """Authorize the admin discount given"""
        if "admin_discount_percentage" in inputs and not info.context.user.has_perm(
            "change_production", target_performance.production
        ):
            raise AuthorizationException(
                message="You do not have permission to assign an admin discount",
                field="admin_discount_percentage",
            )

    class Meta:
        form_class = BookingForm
        create_ability = AllwaysPasses
        update_ability = ModifyBooking


class DeleteBooking(ModelDeletionMutation):
    """Deletes a given booking.

    Must be in-progress, with no associated transactions.

    Args:
        booking_id (str): Global id of the booking to delete
    """

    @classmethod
    def authorize_request(cls, _, info, **inputs):
        booking = cls.get_instance(inputs["id"])
        if not booking.status == Payable.Status.IN_PROGRESS:
            raise GQLException(
                f"This booking is not in progress (Status: {booking.status})"
            )

        # Must have no transactions
        if booking.transactions.count() > 0:
            raise GQLException(
                "This booking cannot be deleted as it has transactions associated with it"
            )
        return super().authorize_request(_, info, **inputs)

    class Meta:
        ability = ModifyBooking
        model = Booking


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
        id = IdInputField(required=True)
        price = graphene.Int(required=True)
        nonce = graphene.String(required=False)
        payment_provider = graphene.Argument(
            "uobtheatre.payments.schema.PaymentProviderEnum"
        )
        device_id = graphene.String(required=False)
        idempotency_key = graphene.String(required=False)
        verify_token = graphene.String(required=False)

    @classmethod
    def resolve_mutation(  # pylint: disable=too-many-arguments, too-many-branches
        cls,
        _,
        info,
        price,
        nonce=None,
        payment_provider=SquareOnline.name,
        device_id=None,
        idempotency_key=None,
        verify_token=None,
        **kwargs,
    ):

        # Get the performance and if it doesn't exist throw an error
        booking = Booking.objects.get(id=kwargs["id"])

        # Verify user can access booking
        if not ModifyBooking.user_has_for(info.context.user, booking):
            raise AuthorizationException(
                message="You do not have permission to modify this booking",
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
        performance (str): The id of the performance that the ticket is
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
        performance = IdInputField(required=True)
        tickets = graphene.List(TicketIDInput, required=True)

    @classmethod
    def resolve_mutation(cls, _, info, booking_reference, tickets, performance):
        performance = Performance.objects.get(id=performance)
        booking = Booking.objects.get(reference=booking_reference)

        # check if the booking pertains to the correct performance
        if booking.performance != performance:
            raise GQLException(
                field="performance",
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
        performance (str): The id of the performance that the ticket is
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
        performance = IdInputField(required=True)
        tickets = graphene.List(TicketIDInput, required=True)

    @classmethod
    def resolve_mutation(cls, _, info, booking_reference, tickets, performance):
        performance = Performance.objects.get(id=performance)
        booking = Booking.objects.get(reference=booking_reference)

        # check if the booking pertains to the correct performance
        if booking.performance != performance:
            # raise booking performance does not match performance given
            raise GQLException(
                field="performance",
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


class CreateBookingTransfer(AuthRequiredMixin, SafeMutation):
    """Mutation to transfer a booking to a difference performance. This creates
    an inprogress booking (transfer) which is linked to the orignal booking via
    transferred_to.

    Args:
        booking_id (str): The gloabl id of the Booking to transfer.
        performance_id (str): The gloabl id of the performance which the
            Booking should be transferred to.

    Returns:
        booking (BookingNode): The Booking for the new performance.

    Raises:
        GQLException: If the Payment was unsucessful.
    """

    booking = graphene.Field(BookingNode)

    class Arguments:
        booking_id = IdInputField(required=True)
        performance_id = IdInputField(required=True)

    @classmethod
    def resolve_mutation(  # pylint: disable=too-many-branches
        cls,
        _,
        info,
        booking_id,
        performance_id,
    ):
        booking = Booking.objects.get(pk=booking_id, user=info.context.user.id)
        performance = Performance.objects.get(pk=performance_id)

        if not BookForPerformance.user_has_for(info.context.user, performance):
            raise AuthorizationException(
                "You do not have permission to create a booking for this performance"
            )

        new_booking = booking.create_transfer(performance)
        return CreateBookingTransfer(booking=new_booking)


class Mutation(graphene.ObjectType):
    """Mutations for bookings"""

    booking = BookingMutation.Field()
    delete_booking = DeleteBooking.Field()
    pay_booking = PayBooking.Field()
    check_in_booking = CheckInBooking.Field()
    uncheck_in_booking = UnCheckInBooking.Field()
    create_booking_transfer = CreateBookingTransfer.Field()
