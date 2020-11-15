from rest_framework import serializers

from uobtheatre.bookings.models import Booking


class CreateBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = "__all__"
