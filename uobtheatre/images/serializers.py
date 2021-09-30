from rest_framework.serializers import CharField, ModelSerializer

from uobtheatre.images.models import Image


class ImageSerializer(ModelSerializer):
    id = CharField(source="global_id")

    class Meta:
        model = Image
        fields = ("id", "file", "alt_text")
        extra_kwargs = {"id": {"read_only": True}}
