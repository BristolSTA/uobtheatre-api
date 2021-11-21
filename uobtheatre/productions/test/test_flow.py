#pylint: disable=R0914

import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.productions.models import Performance, PerformanceSeatGroup
from uobtheatre.societies.test.factories import SocietyFactory
from uobtheatre.venues.test.factories import SeatGroupFactory, VenueFactory


@pytest.mark.django_db
def test_total_production_creation_workflow(gql_client):
    gql_client.login()
    society = SocietyFactory()
    assign_perm("societies.add_production", gql_client.user, society)

    # Step 1: Create production
    example_image_id = to_global_id("ImageNode", ImageFactory().id)

    request = """
        mutation {
          production(
            input: {
                name: "My Production Name"
                featuredImage: "%s"
                posterImage: "%s"
                society: "%s"
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
        to_global_id("SocietyNode", society.id),
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

    performance_gid = to_global_id("PerformanceNode", Performance.objects.first().id)

    # Step 3: Query available seat groups, and set seat groups
    venue = VenueFactory()
    seat_group_1 = SeatGroupFactory(name="Best Seats", venue=venue, capacity=100)
    seat_group_2 = SeatGroupFactory(name="Meh Seats", venue=venue, capacity=50)

    request = (
        """
        query {
            venue(slug: "%s") {
                seatGroups {
                    edges {
                        node {
                            name
                        }
                    }
                }
            }
        }
    """
        % venue.slug
    )

    response = gql_client.execute(request)
    assert response["data"]["venue"]["seatGroups"]["edges"] == [
        {"node": {"name": "Best Seats"}},
        {"node": {"name": "Meh Seats"}},
    ]

    for seat_group in [seat_group_1, seat_group_2]:
        request = """
            mutation {
                performanceSeatGroup(input: {
                    performance: "%s"
                    price: 1000
                    seatGroup: "%s"
                }) {
                    success
                }
            }
        """ % (
            performance_gid,
            to_global_id("SeatGroupNode", seat_group.id),
        )

        response = gql_client.execute(request)
        assert response["data"]["performanceSeatGroup"]["success"] is True

    assert PerformanceSeatGroup.objects.count() == 2

    # Step 4: Assign discounts and concessions
    discounts_to_make = (
        ("Adult", 0),
        ("Student", 0.2),
    )

    for discount in discounts_to_make:
        # 4.1 Create concession
        request = (
            """
            mutation {
                concessionType(input: {
                    name: "%s"
                }) {
                    success
                    concessionType {
                        id
                    }
                }
            }
        """
            % discount[0]
        )

        response = gql_client.execute(request)
        assert response["data"]["concessionType"]["success"] is True
        concession_type_gid = response["data"]["concessionType"]["concessionType"]["id"]

        # 4.2 Create discount
        request = """
            mutation {
                discount(input: {
                    percentage: %s
                    performances: ["%s"]
                    seatGroup: "%s"
                }) {
                    success
                    discount {
                        id
                    }
                }
            }
        """ % (
            discount[1],
            performance_gid,
            to_global_id("SeatGroupNode", seat_group_1.id),
        )

        response = gql_client.execute(request)
        assert response["data"]["discount"]["success"] is True
        discount_gid = response["data"]["discount"]["discount"]["id"]

        # 4.3 Create discount requirement
        request = """
            mutation {
                discountRequirement(input: {
                    concessionType: "%s"
                    discount: "%s"
                    number: 1
                }) {
                    success
                }
            }
        """ % (
            concession_type_gid,
            discount_gid,
        )

        response = gql_client.execute(request)
        assert response["data"]["discountRequirement"]["success"] is True

    # Assert against performance
    performance = Performance.objects.first()
    assert performance.total_capacity == 150
