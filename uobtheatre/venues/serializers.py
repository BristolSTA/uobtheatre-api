from rest_framework import serializers

from uobtheatre.addresses.serializers import AddressSerializer
from uobtheatre.venues.models import SeatGroup, Venue


class FullVenueSerializer(serializers.ModelSerializer):
    address = AddressSerializer()

    class Meta:
        model = Venue
        fields = [
            "id",
            "name",
            "description",
            "image",
            "address",
            "publicly_listed",
            "slug",
        ]


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "publicly_listed", "slug"]


class SeatGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeatGroup
        fields = "__all__"
