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
            	name
                logo {
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
                            "name": society.name,
                            "logo": None,
                            "productions": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": gql_id(
                                                production.id, "ProductionNode"
                                            )
                                        }
                                    }
                                    for production in reversed(
                                        society_productions[index]
                                    )
                                ]
                            },
                        }
                    }
                    for index, society in enumerate(societies)
                ]
            }
        }
    }
