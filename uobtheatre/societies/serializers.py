from rest_framework import serializers
from uobtheatre.societies.models import (
    Society,
)


class SocietySerializer(serializers.ModelSerializer):
    class Meta:
        model = Society
        fields = "__all__"
