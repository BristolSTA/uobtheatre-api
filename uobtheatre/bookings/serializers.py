from rest_framework import serializers

from uobtheatre.bookings.models import Booking
from uobtheatre.productions.serializers import PerformanceSerializer

class CreateBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = "__all__"


class UserBookingGetSerialiser(serializers.ModelSerializer):
    performance = PerformanceSerializer()
    
    class Meta:
        model = Booking
        fields = (
            "id",
            "user",
            "booking_reference",
            "performance",
        )

