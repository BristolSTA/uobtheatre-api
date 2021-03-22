import pytest

from uobtheatre.societies.test.factories import SocietyFactory


@pytest.mark.django_db
def test_image_schema(gql_client):
    society = SocietyFactory()
    response = gql_client.execute(
        """
        {
	  societies {
            edges {
              node {
                logo {
                  url
                  altText
                }
              }
            }
          }
        }
        """
    )

    assert response == {
        "data": {
            "societies": {
                "edges": [
                    {
                        "node": {
                            "logo": {
                                "url": society.logo.file.url,
                                "altText": society.logo.alt_text,
                            },
                        }
                    }
                ]
            }
        }
    }
