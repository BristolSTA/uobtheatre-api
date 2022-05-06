from unittest.mock import patch

import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.discounts.abilities import CreateConcessionType, ModifyConcessionType
from uobtheatre.discounts.models import ConcessionType, Discount, DiscountRequirement
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountFactory,
    DiscountRequirementFactory,
)
from uobtheatre.productions.abilities import EditProduction
from uobtheatre.productions.test.factories import PerformanceFactory

#####
#   Concession Type
#####


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
@pytest.mark.parametrize("with_permission", [(True), (False)])
def test_concession_type_mutation_update(gql_client, with_permission):
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
        ModifyConcessionType, "user_has_for", return_value=with_permission
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called()
        assert response["data"]["concessionType"]["success"] is with_permission
        if with_permission:
            assert response["data"]["concessionType"]["concessionType"] == {
                "name": "Bar"
            }
            assert ConcessionType.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [(True), (False)])
def test_delete_concession_type_mutation(gql_client, with_permission):
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
        ModifyConcessionType, "user_has_for", return_value=with_permission
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called()
        assert response["data"]["deleteConcessionType"]["success"] is with_permission
        if with_permission:
            assert ConcessionType.objects.count() == 0


#####
#   Discount
#####


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [(True), (False)])
def test_discount_mutation_create(gql_client, with_permission):
    performance = PerformanceFactory()
    request = """
        mutation {
          discount(
            input: {
                percentage: 0.2
                performances: ["%s"]
             }
          ) {
            success
         }
        }
    """ % to_global_id(
        "PerformanceNode", performance.id
    )

    with patch.object(
        EditProduction, "user_has_for", return_value=with_permission
    ) as mock:
        response = gql_client.login().execute(request)
        mock.assert_called_once_with(gql_client.user, performance.production)

    assert response["data"]["discount"]["success"] is with_permission


@pytest.mark.django_db
def test_discount_mutation_create_no_performance(gql_client):
    request = """
        mutation {
          discount(
            input: {
                percentage: 0.2
             }
          ) {
            success
         }
        }
    """

    response = gql_client.login().execute(request)

    assert response["data"]["discount"]["success"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [(True), (False)])
def test_discount_mutation_update(gql_client, with_permission):
    performance = PerformanceFactory()
    discount = DiscountFactory()
    discount.performances.set([performance])

    request = """
        mutation {
          discount(
            input: {
                id: "%s"
                percentage: 0.2
             }
          ) {
            success
         }
        }
    """ % to_global_id(
        "DiscountNode", discount.id
    )

    with patch.object(
        EditProduction, "user_has_for", return_value=with_permission
    ) as mock:
        response = gql_client.login().execute(request)
        mock.assert_called_once_with(gql_client.user, performance.production)

    assert response["data"]["discount"]["success"] is with_permission


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [(True), (False)])
def test_delete_discount_mutation(gql_client, with_permission):
    performance = PerformanceFactory()
    discount = DiscountFactory()
    discount.performances.set([performance])

    request = """
        mutation {
          deleteDiscount(id: "%s") {
            success
         }
        }
    """ % (
        to_global_id("DiscountNode", discount.id),
    )

    with patch.object(
        EditProduction, "user_has_for", return_value=with_permission
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called_once_with(gql_client.user, performance.production)
        assert response["data"]["deleteDiscount"]["success"] is with_permission
        assert Discount.objects.count() == 0 if with_permission else 1


#####
#   Discount Requirement
#####


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [(True), (False)])
def test_discount_requirement_mutation_create(gql_client, with_permission):
    discount = DiscountFactory()
    performance = PerformanceFactory()
    discount.performances.set([performance])
    concession_type = ConcessionTypeFactory()
    request = """
        mutation {
          discountRequirement(
            input: {
                discount: "%s"
                number: 1
                concessionType: "%s"
             }
          ) {
            success
         }
        }
    """ % (
        to_global_id("DiscountNode", discount.id),
        to_global_id("ConcessionTypeNode", concession_type.id),
    )

    with patch.object(
        EditProduction, "user_has_for", return_value=with_permission
    ) as mock:
        response = gql_client.login().execute(request)
        mock.assert_called_once_with(gql_client.user, performance.production)

    assert response["data"]["discountRequirement"]["success"] is with_permission


@pytest.mark.django_db
def test_discount_requirement_mutation_create_no_discount(gql_client):
    concession_type = ConcessionTypeFactory()
    request = """
        mutation {
          discountRequirement(
            input: {
                number: 1
                concessionType: "%s"
             }
          ) {
            success
         }
        }
    """ % (
        to_global_id("ConcessionTypeNode", concession_type.id),
    )

    response = gql_client.login().execute(request)

    assert response["data"]["discountRequirement"]["success"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [(True), (False)])
def test_discount_requirement_mutation_update(gql_client, with_permission):
    discount_1 = DiscountFactory()
    performance_1 = PerformanceFactory()
    discount_1.performances.set([performance_1])
    discount_requirement = DiscountRequirementFactory(number=1, discount=discount_1)
    discount_2 = DiscountFactory()
    performance_2 = PerformanceFactory()
    discount_2.performances.set([performance_2])

    request = """
        mutation {
          discountRequirement(
            input: {
                id: "%s"
                number: 2
                discount: "%s"
             }
          ) {
            success
            discountRequirement {
                number
                discount {
                    id
                }
            }
         }
        }
    """ % (
        to_global_id("DiscountRequirementNode", discount_requirement.id),
        to_global_id("DiscountNode", discount_2.id),
    )

    with patch.object(
        EditProduction, "user_has_for", return_value=with_permission
    ) as mock:
        response = gql_client.login().execute(request)
        mock.assert_any_call(gql_client.user, performance_1.production)
        if with_permission:
            mock.assert_any_call(gql_client.user, performance_2.production)

    assert response["data"]["discountRequirement"]["success"] is with_permission


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [(True), (False)])
def test_delete_discount_requirement_mutation(gql_client, with_permission):
    performance = PerformanceFactory()
    discount = DiscountFactory()
    discount.performances.set([performance])
    discount_requirement = DiscountRequirementFactory(discount=discount)

    request = """
        mutation {
          deleteDiscountRequirement(id: "%s") {
            success
         }
        }
    """ % (
        to_global_id("DiscountRequirementNode", discount_requirement.id),
    )

    with patch.object(
        EditProduction, "user_has_for", return_value=with_permission
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called_once_with(gql_client.user, performance.production)
        assert (
            response["data"]["deleteDiscountRequirement"]["success"] is with_permission
        )
        assert DiscountRequirement.objects.count() == 0 if with_permission else 1
