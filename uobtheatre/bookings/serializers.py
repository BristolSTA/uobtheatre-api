from rest_framework import serializers

from uobtheatre.bookings.models import Booking, Ticket
from uobtheatre.productions.serializers import PerformanceSerializer
from uobtheatre.utils.serializers import AppendIdSerializerMixin, UserIdSerializer


class CreateBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = "__all__"


class BookingSerialiser(AppendIdSerializerMixin, serializers.ModelSerializer):
    """ Booking serializer to create booking """

    performance = PerformanceSerializer()
    user_id = UserIdSerializer()

    class Meta:
        model = Booking
        fields = (
            "id",
            "user_id",
            "booking_reference",
            "performance",
        )


class CreateTicketSerializer(AppendIdSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = (
            "seat_group",
            "consession_type",
        )


class CreateBookingSerialiser(AppendIdSerializerMixin, serializers.ModelSerializer):
    """ Booking serializer to create booking """

    tickets = CreateTicketSerializer(many=True, required=False)

    def create(self, validated_data):
        # Extract seating bookings from booking
        tickets = validated_data.pop("tickets")
        # Create the booking
        booking = Booking.objects.create(user=self.context["user"], **validated_data)

        # Create all the seat bookings
        for ticket in tickets:
            Ticket.objects.create(booking=booking, **ticket)

        return booking

    class Meta:
        model = Booking
        fields = ("performance", "tickets")
