from PIL import Image as PILImage
import tempfile
import json
import pytest

from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO

from uobtheatre.images.serializers import ImageSerializer
from uobtheatre.images.models import Image


@pytest.mark.django_db
def test_image_serializer():
    image = PILImage.new("RGB", (100, 100))
    tmp_file = tempfile.NamedTemporaryFile(suffix=".png")
    image.save(tmp_file)

    with open(tmp_file.name, "rb") as temp_file:
        tmp_file.seek(0)
        byio = BytesIO(temp_file.read())
        inm_file = InMemoryUploadedFile(
            file=byio,
            field_name="avatar",
            name="testImage.png",
            content_type="image/png",
            size=byio.getbuffer().nbytes,
            charset=None,
        )

        data = {"file": inm_file}
        serialzier = ImageSerializer(data=data)

        assert serialzier.is_valid()
        serialzier.save()

    assert Image.objects.count() == 1
