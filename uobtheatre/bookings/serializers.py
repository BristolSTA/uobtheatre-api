from rest_framework import serializers

from uobtheatre.bookings.models import Booking, SeatBooking
from uobtheatre.productions.serializers import PerformanceSerializer
from uobtheatre.utils.serializers import AppendIdSerializerMixin


class CreateBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = "__all__"


class BookingSerialiser(AppendIdSerializerMixin, serializers.ModelSerializer):
    """ Booking serializer to create booking """

    performance = PerformanceSerializer()
    user_id = serializers.UUIDField(
        format="hex_verbose",
        source="user.id",
    )

    class Meta:
        model = Booking
        fields = (
            "id",
            "user_id",
            "booking_reference",
            "performance",
        )


class CreateSeatBookingSerializer(AppendIdSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = SeatBooking
        fields = (
            "seat_group",
            "consession_type",
        )


class CreateBookingSerialiser(AppendIdSerializerMixin, serializers.ModelSerializer):
    """ Booking serializer to create booking """

    seat_bookings = CreateSeatBookingSerializer(many=True)

    def create(self, validated_data):
        # Extract seating bookings from booking
        seat_bookings = validated_data.pop("seat_bookings")
        # Create the booking
        booking = Booking.objects.create(**validated_data)

        # Create all the seat bookings
        for seat_booking in seat_bookings:
            SeatBooking.objects.create(booking=booking, **seat_booking)

        return booking

    class Meta:
        model = Booking
        fields = ("user", "performance", "seat_bookings")
