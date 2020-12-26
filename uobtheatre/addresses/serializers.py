from rest_framework import serializers

from uobtheatre.addresses.models import Address


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["street", "city", "postcode", "latitude", "longitude"]
