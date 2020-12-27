from rest_framework import serializers

from uobtheatre.addresses.models import Address


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["building_name", "building_number", "street", "city", "postcode", "latitude", "longitude"]
