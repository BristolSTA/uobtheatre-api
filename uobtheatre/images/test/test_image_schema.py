import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.images.test.factories import ImageFactory


@pytest.mark.django_db
def test_image_schema(gql_client):
    image = ImageFactory()
    response = gql_client.execute(
        """
        {
          images {
            id
            url
            altText
          }
        }
        """
    )

    assert response == {
        "data": {
            "images": [
                {
                    "id": to_global_id("ImageNode", image.id),
                    "url": image.file.url,
                    "altText": image.alt_text,
                }
            ]
        }
    }
