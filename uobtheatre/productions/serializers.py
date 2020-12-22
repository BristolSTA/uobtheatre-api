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

    class Meta:
        model = Performance
        fields = "__all__"


class ProductionSerializer(AppendIdSerializerMixin, serializers.ModelSerializer):
    society = SocietySerializer()
    performances = PerformanceSerializer(many=True)
    warnings = serializers.StringRelatedField(many=True)
    crew = CrewMemberSerialzier(many=True)
    cast = CastMemberSerialzier(many=True)
    start_date = serializers.DateTimeField("iso-8601")
    end_date = serializers.DateTimeField("iso-8601")
    slug = serializers.CharField()

    class Meta:
        model = Production
        fields = "__all__"


class PerformanceTicketTypesSerializer(serializers.ModelSerializer):
    def to_representation(self, performance):
        return {
            "ticket_types": [
                {
                    "seat_group_name": seat_group.name,
                    "consession_types": [
                        {
                            "consession_name": consession.name,
                            "price": (
                                1 - performance.get_conession_discount(consession)
                            )
                            * seating.price,
                        }
                        for consession in performance.consessions()
                    ],
                }
                for seating in performance.seating.all()
                for seat_group in seating.seat_group.all()
            ]
        }
