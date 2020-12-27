import math

from rest_framework import serializers

from uobtheatre.productions.models import (
    CastMember,
    CrewMember,
    Performance,
    Production,
    Venue,
    Warning,
)
from uobtheatre.societies.serializers import SocietySerializer
from uobtheatre.utils.serializers import AppendIdSerializerMixin
from uobtheatre.venues.serializers import VenueSerializer


class CrewMemberSerialzier(serializers.ModelSerializer):
    role = serializers.StringRelatedField()

    class Meta:
        model = CrewMember
        fields = ("name", "role")


class CastMemberSerialzier(serializers.ModelSerializer):
    class Meta:
        model = CastMember
        fields = ("name", "role", "profile_picture")


class WarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warning
        fields = "__all__"


class PerformanceSerializer(AppendIdSerializerMixin, serializers.ModelSerializer):
    venue = VenueSerializer()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()

    class Meta:
        model = Performance
        fields = ("id", "production", "venue", "start", "end", "extra_information")


class ProductionSerializer(AppendIdSerializerMixin, serializers.ModelSerializer):
    society = SocietySerializer()
    performances = PerformanceSerializer(many=True)
    warnings = serializers.StringRelatedField(many=True)
    crew = CrewMemberSerialzier(many=True)
    cast = CastMemberSerialzier(many=True)
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()

    class Meta:
        model = Production
        fields = "__all__"
        lookup_field = "email"


class PerformanceTicketTypesSerializer(serializers.ModelSerializer):
    def to_representation(self, performance):
        return {
            "ticket_types": [
                {
                    "seat_group": {
                        "name": seat_group.name,
                        "id": seat_group.id,
                    },
                    "consession_types": [
                        {
                            "consession": {
                                "name": consession.name,
                                "id": consession.id,
                            },
                            "price": performance.price_with_consession(
                                consession, seating.price
                            ),
                            "price_pounds": "%.2f"
                            % (
                                performance.price_with_consession(
                                    consession, seating.price
                                )
                                / 100
                            ),
                        }
                        for consession in performance.consessions()
                    ],
                }
                for seating in performance.seating.order_by("id")
                for seat_group in seating.seat_groups.order_by("id")
            ]
        }
