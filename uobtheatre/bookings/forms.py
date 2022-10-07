from typing import Optional

import graphene
from django.forms import CharField, Field, ValidationError
from graphene_django.forms.converter import convert_form_field

from uobtheatre.bookings.models import Booking, Ticket
from uobtheatre.discounts.models import ConcessionType
from uobtheatre.payments.payables import Payable
from uobtheatre.users.models import User
from uobtheatre.utils.exceptions import GQLException
from uobtheatre.utils.forms import MutationForm
from uobtheatre.utils.schema import IdInputField
from uobtheatre.venues.models import Seat, SeatGroup


class TicketInputType(graphene.InputObjectType):
    """Input for creating Tickets with mutations."""

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


class TicketListInputField(Field):
    pass


@convert_form_field.register(TicketListInputField)
def convert_form_field_to_string(field):
    return graphene.List(
        TicketInputType, description=field.help_text, required=field.required
    )


class BookingForm(MutationForm):
    """Form for creating/updating a booking"""

    tickets = TicketListInputField(required=False)
    user_email = CharField(required=False)

    def clean(self):
        """Validate and clean form data"""
        cleaned_data = super().clean()

        if not self.instance.creator_id:
            # If the instance has no creater, the current user is the creator
            self.instance.creator = self.user

        # We only update the booking's user if an email has be explicitly provided, or no user is currently assigned to it
        if user_email := cleaned_data.get("user_email"):
            # If a user is supplied to assign the booking to, create or retrieve that user
            self.instance.user, _ = User.objects.get_or_create(
                email=user_email,
                defaults={"first_name": "Anonymous", "last_name": "User"},
            )
        elif not self.instance.id:
            # If no exisiting user on booking, set it to be the creator (current user)
            self.instance.user = self.user

        ## Check tickets
        if cleaned_data.get("tickets") is not None:
            self._clean_tickets(cleaned_data)

    @staticmethod
    def _max_tickets_per_booking(user, performance) -> Optional[int]:
        """
        Work out the maximum number of tickets the user is able to have in a booking for the given performance

        Returns the number of tickets, or None if they have no limit
        """
        max_tickets: Optional[int] = 10
        if user.has_perm("boxoffice", performance.production):
            max_tickets = None

        return max_tickets

    def _clean_tickets(self, cleaned_data):
        """Cleans and validates the supplied ticket data"""
        (
            self.cleaned_data["add_tickets"],
            self.cleaned_data["delete_tickets"],
            total_number_of_tickets,
        ) = self.instance.get_ticket_diff(
            map(lambda ticket: ticket.to_ticket(), cleaned_data.get("tickets"))
        )

        max_tickets = self._max_tickets_per_booking(
            self.user, cleaned_data.get("performance")
        )

        if max_tickets and total_number_of_tickets > max_tickets:
            raise ValidationError(
                {"tickets": f"You may only book a maximum of {max_tickets} tickets"}
            )

        # Check the capacity of the performance and its seat_groups
        try:
            cleaned_data.get("performance").validate_tickets(
                self.cleaned_data["add_tickets"], self.cleaned_data["delete_tickets"]
            )
        except GQLException as err:
            raise ValidationError({"tickets": err.message}) from err

    def save(self, *args, **kwargs):
        """Overrides the default form save to enforce 1 in-progress booking per performance per user"""

        # If creating a new model, or the target user has been changed, delete existing draft bookings
        if self.is_creation or self.cleaned_data["user_email"]:
            bookings = self.instance.user.bookings

            # Exclude this booking if it has been created already
            if not self.is_creation:
                bookings = bookings.exclude(id=self.instance.id)

            bookings.filter(
                status=Payable.Status.IN_PROGRESS,
                performance_id=self.instance.performance.id,
            ).delete()

        return super().save(*args, **kwargs)

    def _save_m2m(self):
        """Save the many-to-many relations"""
        super()._save_m2m()
        for ticket in self.cleaned_data.get("add_tickets", []):
            ticket.booking = self.instance
            ticket.save()

        for ticket in self.cleaned_data.get("delete_tickets", []):
            ticket.delete()

    class Meta:
        model = Booking
        fields = ("performance", "admin_discount_percentage", "accessibility_info")
