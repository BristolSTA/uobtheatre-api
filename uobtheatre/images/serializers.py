from rest_framework.serializers import ModelSerializer

from uobtheatre.images.models import Image


class ImageSerializer(ModelSerializer):
    class Meta:
        model = Image
        fields = ("global_id", "file", "alt_text")
        extra_kwargs = {"gloal_id": {"read_only": True}}
