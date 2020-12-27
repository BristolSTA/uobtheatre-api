from rest_framework import serializers

from uobtheatre.venues.models import Venue
from uobtheatre.addresses.serializers import AddressSerializer


class FullVenueSerializer(serializers.ModelSerializer):
    address = AddressSerializer()

    class Meta:
        model = Venue
        fields = ["id", "name", "description", "address", "slug"]


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "slug"]
