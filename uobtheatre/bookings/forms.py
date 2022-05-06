import graphene
from django.forms import CharField, Field, ValidationError
from graphene_django.forms.converter import convert_form_field

from uobtheatre.bookings.models import Booking, Ticket, max_tickets_per_booking
from uobtheatre.discounts.models import ConcessionType
from uobtheatre.payments.payables import Payable
from uobtheatre.users.models import User
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


class TicketInputField(Field):
    pass


@convert_form_field.register(TicketInputField)
def convert_form_field_to_string(field):
    return graphene.List(
        TicketInputType, description=field.help_text, required=field.required
    )


class BookingForm(MutationForm):
    """Form for creating/updating a booking"""

    tickets = TicketInputField(required=False)
    user_email = CharField(required=False)

    def clean(self):
        """Validate form data on clean"""
        cleaned_data = super().clean()
        ## Various fields
        if not self.instance.creator_id:
            self.instance.creator = self.user

        if cleaned_data.get("user_email"):
            target_user, _ = User.objects.get_or_create(
                email=cleaned_data.get("user_email"),
                defaults={"first_name": "Anonymous", "last_name": "User"},
            )
        else:
            target_user = self.user

        if cleaned_data.get("user_email") or not self.instance.user_id:
            self.instance.user = target_user

        ## Check tickets
        if cleaned_data.get("tickets") is not None:
            ticket_objects = list(
                map(lambda ticket: ticket.to_ticket(), cleaned_data.get("tickets"))
            )

            (
                add_tickets,
                delete_tickets,
                total_number_of_tickets,
            ) = self.instance.get_ticket_diff(ticket_objects)

            self.cleaned_data["add_tickets"] = add_tickets
            self.cleaned_data["delete_tickets"] = delete_tickets

            if (
                total_number_of_tickets > max_tickets_per_booking()
                and not self.user.has_perm(
                    "boxoffice", cleaned_data.get("performance").production
                )
            ):
                raise ValidationError(
                    {
                        "tickets": "You may only book a maximum of %s tickets"
                        % max_tickets_per_booking()
                    }
                )

            # Check the capacity of the show and its seat_groups
            err = cleaned_data.get("performance").check_capacity(ticket_objects)
            if err:
                raise ValidationError({"tickets": err})

    def save(self, *args, **kwargs):
        """Overrides the default form save to setup users (from provided emails)"""
        if not self.instance.id or self.cleaned_data["user_email"]:
            # Delete existing draft bookings
            bookings = self.instance.user.bookings
            if self.instance.id:
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
        fields = (
            "performance",
            "admin_discount_percentage",
        )
