import tempfile

import pytest
from graphql_relay.node.node import to_global_id
from PIL import Image as PILImage

from uobtheatre.images.models import Image


@pytest.mark.django_db
def test_image_upload(rest_client):
    """
    Test trying to add a photo
    """

    # Create image
    image = PILImage.new("RGB", (100, 100))
    tmp_file = tempfile.NamedTemporaryFile(  # pylint: disable=consider-using-with
        suffix=".jpg"
    )
    image.save(tmp_file)

    # Send data
    with open(tmp_file.name, "rb") as data:
        response = rest_client.post(
            "/upload/",
            {"file": data},
            format="multipart",
        )

    assert Image.objects.count() == 1
    image = Image.objects.first()

    assert response.status_code == 201
    assert response.json() == {
        "alt_text": None,
        "file": image.file.url,
        "global_id": to_global_id("ImageNode", image.id),
    }


@pytest.mark.django_db
def test_image_upload_invalid(rest_client):
    response = rest_client.post(
        "/upload/",
        {},
        format="multipart",
    )

    assert response.status_code == 400
