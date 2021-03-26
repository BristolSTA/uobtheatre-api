import pytest

from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.societies.test.factories import SocietyFactory


@pytest.mark.django_db
def test_societies_schema(gql_client, gql_id):
    societies = [SocietyFactory() for i in range(3)]
    society_productions = [
        [ProductionFactory(society=society) for i in range(10)] for society in societies
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
                            "id": gql_id(society.id, "SocietyNode"),
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
                            "productions": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": gql_id(
                                                production.id, "ProductionNode"
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
def test_slug_single_schema(gql_client, gql_id):
    societies = [SocietyFactory() for i in range(2)]

    request = """
        query {
	  society(slug:"%s") {
            id
          }
        }

        """
    response = gql_client.execute(request % "")

    assert response["errors"][0]["message"] == "Society matching query does not exist."
    assert response["data"] == {"society": None}

    response = gql_client.execute(request % societies[0].slug)
    assert response["data"] == {
        "society": {"id": gql_id(societies[0].id, "SocietyNode")}
    }
