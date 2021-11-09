import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.productions.models import Performance, Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.venues.test.factories import VenueFactory


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [True, False])
def test_production_mutation_create(gql_client, with_permission):
    example_image_id = to_global_id("ImageNode", ImageFactory().id)

    request = """
        mutation {
          production(
            input: {
                name: "My Production Name"
                featuredImage: "%s"
                posterImage: "%s"
                description: "My great show!"
             }
          ) {
            success
            production {
                name
                subtitle
            }
         }
        }
    """ % (
        example_image_id,
        example_image_id,
    )

    gql_client.login()
    if with_permission:
        assign_perm("productions.add_production", gql_client.user)

    response = gql_client.execute(request)
    assert response["data"]["production"]["success"] is with_permission

    if with_permission:
        assert response["data"]["production"]["production"] == {
            "name": "My Production Name",
            "subtitle": None,
        }
        assert Production.objects.count() == 1


@pytest.mark.django_db
def test_production_mutation_create_with_missing_info(gql_client):
    request = """
        mutation {
          production(
            input: {
                name: "My Production Name"
                description: "My great show!"
             }
          ) {
            success
            errors {
                ...on FieldError {
                    message
                    field
                }
            }
         }
        }
    """

    gql_client.login()
    assign_perm("productions.add_production", gql_client.user)

    response = gql_client.execute(request)
    assert response["data"]["production"]["success"] is False
    assert response["data"]["production"]["errors"] == [
        {"message": "This field is required.", "field": "posterImage"},
        {"message": "This field is required.", "field": "featuredImage"},
    ]


@pytest.mark.django_db
def test_production_mutation_create_update(gql_client):
    production = ProductionFactory(name="My Old Name", subtitle="My subtitle")

    request = """
        mutation {
          production(
            input: {
                id: "%s"
                name: "My New Name"
             }
          ) {
            success
            production {
                name
                subtitle
            }
            errors {
                ...on FieldError {
                    message
                    field
                }
                ... on NonFieldError {
                    message
                }
            }
         }
        }
    """ % to_global_id(
        "ProductionNode", production.id
    )

    gql_client.login()
    assign_perm("change_production", gql_client.user, production)

    response = gql_client.execute(request)
    assert response["data"]["production"]["success"] is True
    assert response["data"]["production"]["production"] == {
        "name": "My New Name",
        "subtitle": "My subtitle",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [True, False])
def test_performance_mutation_create(gql_client, with_permission):
    production = ProductionFactory(name="My Production")
    request = """
        mutation {
          performance(
            input: {
                doorsOpen: "2021-11-09T00:00:00"
                start: "2021-11-09T00:00:00"
                end: "2021-11-09T00:00:00"
                venue: "%s"
                production: "%s"
             }
          ) {
            success
            performance {
                id
                production {
                    name
                }
            }
            errors {
                ...on FieldError {
                    message
                    field
                }
                ... on NonFieldError {
                    message
                }
            }
         }
        }
    """ % (
        to_global_id("VenueNode", VenueFactory().id),
        to_global_id("ProductionNode", production.id),
    )

    gql_client.login()
    if with_permission:
        assign_perm("productions.change_production", gql_client.user, production)

    response = gql_client.execute(request)
    assert response["data"]["performance"]["success"] is with_permission

    if with_permission:
        assert (
            response["data"]["performance"]["performance"]["production"]["name"]
            == "My Production"
        )
        assert Performance.objects.count() == 1


@pytest.mark.django_db
def test_performance_mutation_create_with_no_production(gql_client):
    request = """
        mutation {
          performance(
            input: {
                doorsOpen: "2021-11-09T00:00:00"
                start: "2021-11-09T00:00:00"
                end: "2021-11-09T00:00:00"
             }
          ) {
            success
            performance {
                id
                production {
                    name
                }
            }
            errors {
                ...on FieldError {
                    message
                    field
                }
                ... on NonFieldError {
                    message
                }
            }
         }
        }
    """

    response = gql_client.login().execute(request)
    assert response["data"]["performance"]["success"] is False
    assert (
        response["data"]["performance"]["errors"][0]["message"]
        == "You are not authorized to perform this action"
    )


@pytest.mark.django_db
def test_performance_mutation_update(gql_client):
    performance = PerformanceFactory()
    gql_client.login().user.assign_perm("change_production", performance.production)
    request = """
        mutation {
          performance(
            input: {
                id: "%s"
                start: "2021-11-10T00:00:00"
             }
          ) {
            success
            performance {
                start
            }
         }
        }
    """ % (
        to_global_id("PerformanceNode", performance.id),
    )

    response = gql_client.execute(request)
    assert response["data"]["performance"]["success"] is True
    assert (
        response["data"]["performance"]["performance"]["start"] == "2021-11-10T00:00:00"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "with_permission,with_bookings", [(True, False), (True, True), (False, False)]
)
def test_delete_performance_mutation(gql_client, with_permission, with_bookings):
    performance = PerformanceFactory()

    if with_bookings:
        BookingFactory(performance=performance)

    request = """
        mutation {
          deletePerformance(
            id: "%s"
          ) {
            success
         }
        }
    """ % to_global_id(
        "PerformanceNode", performance.id
    )

    gql_client.login()
    if with_permission:
        assign_perm("delete_performance", gql_client.user, performance)

    response = gql_client.execute(request)

    should_success = (
        with_permission and not with_bookings
    )  # Deletion should not happen if the user doesn't have the permission, or there are related models associated with the performance that are restricted
    assert response["data"]["deletePerformance"]["success"] is should_success

    if should_success:
        assert Performance.objects.count() == 0


@pytest.mark.django_db
def test_total_production_creation_workflow(gql_client):
    gql_client.login()
    assign_perm("productions.add_production", gql_client.user)

    # Step 1: Create production
    example_image_id = to_global_id("ImageNode", ImageFactory().id)

    request = """
        mutation {
          production(
            input: {
                name: "My Production Name"
                featuredImage: "%s"
                posterImage: "%s"
                description: "My great show!"
             }
          ) {
            success
            production {
                id
            }
            errors {
                ...on FieldError {
                    message
                    field
                }
                ...on NonFieldError {
                    message
                }
            }
         }
        }
    """ % (
        example_image_id,
        example_image_id,
    )

    response = gql_client.execute(request)
    assert response["data"]["production"]["success"] is True

    production_gid = response["data"]["production"]["production"]["id"]

    # Step 2: Create performances

    for i in range(3):
        request = """
            mutation {
            performance(
                input: {
                    production: "%s"
                    venue: "%s"
                    doorsOpen: "2021-11-%sT00:00:00"
                    start: "2021-11-%sT00:00:00"
                    end: "2021-11-%sT00:00:00"
                }
            ) {
                success
            }
            }
        """ % (
            production_gid,
            to_global_id("VenueNode", VenueFactory().id),
            i + 10,
            i + 10,
            i + 10,
        )

        response = gql_client.execute(request)
        assert response["data"]["performance"]["success"] is True
    assert Performance.objects.count() == 3
