from unittest.mock import patch

import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.test.factories import BookingFactory, PerformanceSeatingFactory
from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.productions.abilities import EditProductionObjects
from uobtheatre.productions.models import Performance, PerformanceSeatGroup, Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.societies.test.factories import SocietyFactory
from uobtheatre.venues.test.factories import SeatGroupFactory, VenueFactory

###
# Production Mutations
###


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [True, False])
def test_production_mutation_create(gql_client, with_permission):
    example_image_id = to_global_id("ImageNode", ImageFactory().id)
    society = SocietyFactory()

    request = """
        mutation {
          production(
            input: {
                name: "My Production Name"
                society: "%s"
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
        to_global_id("SocietyNode", society.id),
        example_image_id,
        example_image_id,
    )

    gql_client.login()
    if with_permission:
        assign_perm("societies.add_production", gql_client.user, society)

    response = gql_client.execute(request)
    assert response["data"]["production"]["success"] is with_permission

    if with_permission:
        assert response["data"]["production"]["production"] == {
            "name": "My Production Name",
            "subtitle": None,
        }
        assert Production.objects.count() == 1


@pytest.mark.django_db
def test_production_mutation_create_bad_society(gql_client):
    example_image_id = to_global_id("ImageNode", ImageFactory().id)
    society = SocietyFactory()

    request = """
        mutation {
          production(
            input: {
                name: "My Production Name"
                featuredImage: "%s"
                posterImage: "%s"
                description: "My great show!"
                society: "%s"
             }
          ) {
            success
         }
        }
    """ % (
        example_image_id,
        example_image_id,
        to_global_id("SocietyNode", society.id),
    )

    gql_client.login()
    assign_perm("productions.add_production", gql_client.user)

    response = gql_client.execute(request)
    assert response["data"]["production"]["success"] is False


@pytest.mark.django_db
def test_production_mutation_create_with_missing_info(gql_client):
    request = """
        mutation {
          production(
            input: {
                name: "My Production Name"
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
        {"message": "This field is required.", "field": "society"},
        {"message": "This field is required.", "field": "description"},
    ]


@pytest.mark.django_db
def test_production_mutation_create_update(gql_client):
    production = ProductionFactory(
        name="My Old Name", subtitle="My subtitle", status=Production.Status.DRAFT
    )

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
@pytest.mark.parametrize(
    "has_new_permission,expected_outcome",
    [
        (False, False),
        (True, True),
    ],
)
def test_production_mutation_update_new_society(
    gql_client, has_new_permission, expected_outcome
):
    production = ProductionFactory()
    new_society = SocietyFactory()
    request = """
        mutation {
          production(
            input: {
                id: "%s"
                society: "%s"
             }
          ) {
            success
         }
        }
    """ % (
        to_global_id("ProductionNode", production.id),
        to_global_id("SocietyNode", new_society.id),
    )

    gql_client.login()

    with patch.object(EditProductionObjects, "user_has", return_value=True):
        if has_new_permission:
            assign_perm("add_production", gql_client.user, new_society)

        response = gql_client.execute(request)

    assert response["data"]["production"]["success"] is expected_outcome


###
# Performance Mutations
###


@pytest.mark.django_db
@pytest.mark.parametrize("with_permission", [True, False])
def test_performance_mutation_create(gql_client, with_permission):
    production = ProductionFactory(name="My Production", status=Production.Status.DRAFT)
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
@pytest.mark.parametrize("with_permission", [True, False])
def test_performance_mutation_update(gql_client, with_permission):
    performance = PerformanceFactory()
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

    with patch.object(
        EditProductionObjects, "user_has", return_value=with_permission
    ) as ability_mock:
        response = gql_client.login().execute(request)
        ability_mock.assert_called_with(gql_client.user, performance.production)

    assert response["data"]["performance"]["success"] is with_permission
    if with_permission:
        assert (
            response["data"]["performance"]["performance"]["start"]
            == "2021-11-10T00:00:00+00:00"
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "has_old_permission,has_new_permission,expected_outcome",
    [
        (False, False, False),
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
def test_performance_mutation_update_new_production(
    gql_client, has_old_permission, has_new_permission, expected_outcome
):
    performance = PerformanceFactory()
    new_production = ProductionFactory()
    request = """
        mutation {
          performance(
            input: {
                id: "%s"
                start: "2021-11-10T00:00:00"
                production: "%s"
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
        to_global_id("ProductionNode", new_production.id),
    )

    with patch.object(
        EditProductionObjects,
        "user_has",
        side_effect=[has_new_permission, has_old_permission],
    ) as ability_mock:
        response = gql_client.login().execute(request)
        assert ability_mock.call_count == 2  # To check old and new production
        ability_mock.assert_any_call(gql_client.user, performance.production)
        ability_mock.assert_any_call(gql_client.user, new_production)

    assert response["data"]["performance"]["success"] is expected_outcome
    if expected_outcome:
        assert (
            response["data"]["performance"]["performance"]["start"]
            == "2021-11-10T00:00:00+00:00"
        )


@pytest.mark.django_db
def test_performance_mutation_update_to_unallowed_production(gql_client):
    performance = PerformanceFactory()
    new_production = ProductionFactory()
    request = """
        mutation {
          performance(
            input: {
                id: "%s"
                production: "%s"
             }
          ) {
            success
         }
        }
    """ % (
        to_global_id("PerformanceNode", performance.id),
        to_global_id("ProductionNode", new_production.id),
    )

    with patch.object(
        EditProductionObjects, "user_has", return_value=False
    ) as ability_mock:
        response = gql_client.login().execute(request)
        ability_mock.assert_called()
    assert response["data"]["performance"]["success"] is False


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


###
# Performance Seat Group Mutations
###


@pytest.mark.django_db
def test_performance_seat_group_mutation_create(gql_client):
    sg_gid = to_global_id("SeatGroupNode", SeatGroupFactory().id)
    performance_gid = to_global_id("PerformanceNode", PerformanceFactory().id)
    request = """
        mutation {
          performanceSeatGroup(
            input: {
                seatGroup: "%s"
                performance: "%s"
                price: 1000
             }
          ) {
            success
            performanceSeatGroup {
                performance {
                    id
                }
                seatGroup {
                    id
                }
            }
         }
        }
    """ % (
        sg_gid,
        performance_gid,
    )

    with patch.object(
        EditProductionObjects, "user_has", return_value=True
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called()
        assert response["data"]["performanceSeatGroup"]["success"] is True
        assert response["data"]["performanceSeatGroup"]["performanceSeatGroup"] == {
            "performance": {"id": performance_gid},
            "seatGroup": {"id": sg_gid},
        }


@pytest.mark.django_db
def test_performance_seat_group_mutation_create_no_performance(gql_client):
    sg_gid = to_global_id("SeatGroupNode", SeatGroupFactory().id)
    request = """
        mutation {
          performanceSeatGroup(
            input: {
                seatGroup: "%s"
                price: 1000
             }
          ) {
            success
            performanceSeatGroup {
                performance {
                    id
                }
                seatGroup {
                    id
                }
            }
         }
        }
    """ % (
        sg_gid,
    )

    response = gql_client.login().execute(request)

    assert response["data"]["performanceSeatGroup"]["success"] is False


@pytest.mark.django_db
def test_performance_seat_group_mutation_update(gql_client):
    psg = PerformanceSeatingFactory(price=500)
    request = """
        mutation {
          performanceSeatGroup(
            input: {
                id: "%s"
                price: 1000
             }
          ) {
            success
            performanceSeatGroup {
                price
            }
         }
        }
    """ % (
        to_global_id("PerformanceSeatGroup", psg.id),
    )

    with patch.object(
        EditProductionObjects, "user_has", return_value=True
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called()
        assert response["data"]["performanceSeatGroup"]["success"] is True
        assert response["data"]["performanceSeatGroup"]["performanceSeatGroup"] == {
            "price": 1000
        }


@pytest.mark.django_db
def test_delete_performance_seat_group_mutation(gql_client):
    psg = PerformanceSeatingFactory()
    request = """
        mutation {
          deletePerformanceSeatGroup(id: "%s") {
            success
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
        to_global_id("PerformanceSeatGroup", psg.id),
    )

    with patch.object(
        EditProductionObjects, "user_has", return_value=True
    ) as ability_mock:
        response = gql_client.login().execute(request)

        ability_mock.assert_called()
        assert response["data"]["deletePerformanceSeatGroup"]["success"] is True
        assert PerformanceSeatGroup.objects.count() == 0
