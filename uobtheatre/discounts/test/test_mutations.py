from unittest.mock import patch

import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.discounts.abilities import CreateConcessionType, ModifyConcessionType
from uobtheatre.discounts.models import ConcessionType
from uobtheatre.discounts.test.factories import ConcessionTypeFactory


@pytest.mark.django_db
def test_concession_type_mutation_create(gql_client):
    request = """
        mutation {
          concessionType(
            input: {
                name: "Student"
                description: "ID Required"
             }
          ) {
            success
            concessionType {
                name
                description
            }
         }
        }
    """

    with patch.object(
        CreateConcessionType, "user_has", return_value=True
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called()
        assert response["data"]["concessionType"]["success"] is True
        assert response["data"]["concessionType"]["concessionType"] == {
            "name": "Student",
            "description": "ID Required",
        }


@pytest.mark.django_db
def test_concession_type_mutation_update(gql_client):
    concession_type = ConcessionTypeFactory(name="Foo")
    request = """
        mutation {
          concessionType(
            input: {
                id: "%s"
                name: "Bar"
             }
          ) {
            success
            concessionType {
                name
            }
         }
        }
    """ % (
        to_global_id("ConcessionTypeNode", concession_type.id),
    )

    with patch.object(
        ModifyConcessionType, "user_has", return_value=True
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called()
        assert response["data"]["concessionType"]["success"] is True
        assert response["data"]["concessionType"]["concessionType"] == {"name": "Bar"}
        assert ConcessionType.objects.count() == 1


@pytest.mark.django_db
def test_delete_concession_type_mutation(gql_client):
    concession_type = ConcessionTypeFactory()
    request = """
        mutation {
          deleteConcessionType(id: "%s") {
            success
         }
        }
    """ % (
        to_global_id("ConcessionType", concession_type.id),
    )

    with patch.object(
        ModifyConcessionType, "user_has", return_value=True
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called()
        assert response["data"]["deleteConcessionType"]["success"] is True
        assert ConcessionType.objects.count() == 0
