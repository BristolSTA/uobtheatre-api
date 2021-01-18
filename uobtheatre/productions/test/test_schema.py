import pytest

from uobtheatre.productions.test.factories import ProductionFactory


@pytest.mark.django_db
def test_productions_schema(gql_client):

    production = ProductionFactory()

    body = {"query": {"productions": {"id"}}}
    response = gql_client.execute("""{ productions { id } }""")

    assert response == {
        "data": {
            "productions": [
                {
                    "id": str(production.id),
                }
            ]
        }
    }
