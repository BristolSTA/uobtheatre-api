from rest_framework import serializers
from uobtheatre.productions.models import (
    Production,
    Society,
    Venue,
    Performance,
)


class SocietySerializer(serializers.ModelSerializer):
    class Meta:
        model = Society
        fields = "__all__"


class ProductionSerializer(serializers.ModelSerializer):
    society = SocietySerializer()

    class Meta:
        model = Production
        fields = "__all__"


class PerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Performance
        fields = "__all__"


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = "__all__"
