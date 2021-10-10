import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.societies.test.factories import SocietyFactory


@pytest.mark.django_db
def test_societies_schema(gql_client):
    societies = [SocietyFactory() for _ in range(3)]
    society_productions = [
        [ProductionFactory(society=society) for _ in range(1)] for society in societies
    ]

    response = gql_client.execute(
        """
        {
	  societies {
            edges {
              node {
                id
                createdAt
                updatedAt
            	name
                description
                slug
                logo {
                  url
                }
                banner {
                  url
                }
                website
                contact
                productions {
                  edges {
                    node {
                      id
                    }
                  }
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
                            "id": to_global_id("SocietyNode", society.id),
                            "createdAt": society.created_at.isoformat(),
                            "updatedAt": society.updated_at.isoformat(),
                            "name": society.name,
                            "description": society.description,
                            "slug": society.slug,
                            "logo": {
                                "url": society.logo.file.url,
                            },
                            "banner": {
                                "url": society.banner.file.url,
                            },
                            "website": society.website,
                            "contact": society.contact,
                            "productions": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": to_global_id(
                                                "ProductionNode", production.id
                                            )
                                        }
                                    }
                                    for production in society_productions[index]
                                ]
                            },
                        }
                    }
                    for index, society in enumerate(societies)
                ]
            }
        }
    }


@pytest.mark.django_db
def test_slug_single_schema(gql_client):
    societies = [SocietyFactory() for i in range(2)]

    request = """
        query {
	  society(slug:"%s") {
            id
          }
        }

        """
    response = gql_client.execute(request % "")

    assert not response.get("errors", None)
    assert response["data"] == {"society": None}

    response = gql_client.execute(request % societies[0].slug)
    assert response["data"] == {
        "society": {"id": to_global_id("SocietyNode", societies[0].id)}
    }
