# pylint: disable=R0914,too-many-statements

import pytest
from graphql_relay import from_global_id
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
)
from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.productions.models import Performance, PerformanceSeatGroup, Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.societies.test.factories import SocietyFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.venues.test.factories import SeatGroupFactory, VenueFactory

pytestmark = pytest.mark.system_test


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
                contactEmail: "my@email.com"
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

    # Step 1b: Check it won't let us submit for review
    request = (
        """
        mutation {
            setProductionStatus(productionId: "%s", status: PENDING) {
                success
            }
        }
    """
        % production_gid
    )

    response = gql_client.execute(request)

    assert response["data"]["setProductionStatus"]["success"] is False

    # Step 2: Create performances

    for i in range(3):
        request = """
            mutation {
            performance(
                input: {
                    production: "%s"
                    venue: "%s"
                    doorsOpen: "2021-11-%sT00:00:00"
                    start: "2021-11-%sT00:10:00"
                    end: "2021-11-%sT00:20:00"
                }
            ) {
                success
                performance {
                    id
                }
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

    # Delete all but first performance
    for performance in Performance.objects.all()[1:]:
        request = """
            mutation {
                deletePerformance(id: "%s") {
                    success
                }
            }
        """ % to_global_id(
            "PerformanceNode", performance.id
        )
        response = gql_client.execute(request)
        assert response["data"]["deletePerformance"]["success"] is True

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
    performance = Production.objects.get(
        pk=from_global_id(production_gid)[1]
    ).performances.first()
    assert performance.total_capacity == 150

    # Step 5: Assign permisisons to users
    UserFactory(email="joe.bloggs@example.org")
    request = """
            mutation {
                productionPermissions(
                    id: "%s"
                    userEmail: "joe.bloggs@example.org"
                    permissions: ["boxoffice"]
                ) {
                    success
                }
            }
    """ % (
        production_gid,
    )

    response = gql_client.execute(request)
    assert response["data"]["productionPermissions"]["success"] is True

    # Now try a user that doesn't exist
    request = """
            mutation {
                productionPermissions(
                    id: "%s"
                    userEmail: "joe.bloggs.not.exists@example.org"
                    permissions: ["boxoffice"]
                ) {
                    success
                    errors {
                        ... on FieldError {
                            field
                            message
                        }
                    }
                }
            }
    """ % (
        production_gid,
    )

    response = gql_client.execute(request)
    assert response["data"]["productionPermissions"]["success"] is False
    assert response["data"]["productionPermissions"]["errors"] == [
        {
            "message": "A user with that email does not exist",
            "field": "userEmail",
        }
    ]

    # Step 6: Check it will let us submit for review
    request = (
        """
        mutation {
            setProductionStatus(productionId: "%s", status: PENDING) {
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
    """
        % production_gid
    )

    response = gql_client.execute(request)
    assert response["data"]["setProductionStatus"]["success"] is True


@pytest.mark.django_db
def test_correct_capacities(gql_client):
    venue_capacity = 207
    venue = VenueFactory(internal_capacity=venue_capacity)
    sg_all_capacity = venue_capacity  # 207
    seat_group_all = SeatGroupFactory(venue=venue, capacity=sg_all_capacity)
    sg_small_capacity = 50
    seat_group_small = SeatGroupFactory(venue=venue, capacity=sg_small_capacity)
    sg_best_capacity = 157
    seat_group_best = SeatGroupFactory(venue=venue, capacity=sg_best_capacity)
    production = ProductionFactory()

    perf_1 = PerformanceFactory(production=production, venue=venue)
    PerformanceSeatingFactory(
        performance=perf_1, seat_group=seat_group_all, capacity=sg_all_capacity
    )
    PerformanceSeatingFactory(
        performance=perf_1, seat_group=seat_group_small, capacity=sg_small_capacity
    )
    PerformanceSeatingFactory(
        performance=perf_1, seat_group=seat_group_best, capacity=147
    )

    # check performance with a capacity limit
    performance_limit_capacity = 180
    perf_2 = PerformanceFactory(
        production=production, venue=venue, capacity=performance_limit_capacity
    )
    PerformanceSeatingFactory(
        performance=perf_2, seat_group=seat_group_all, capacity=sg_all_capacity
    )
    PerformanceSeatingFactory(
        performance=perf_2, seat_group=seat_group_small, capacity=sg_small_capacity
    )
    PerformanceSeatingFactory(
        performance=perf_2, seat_group=seat_group_best, capacity=147
    )

    # check performanceSeatGroup limit below performace capacity
    perf_3 = PerformanceFactory(
        production=production, venue=venue, capacity=performance_limit_capacity
    )
    psg_capacity = 170
    PerformanceSeatingFactory(
        performance=perf_3, seat_group=seat_group_all, capacity=psg_capacity
    )

    # booking in small seatgroup should reduce capacity remaining on this seatgroup and
    # any seatgroup with capacity remamining > performance capacity remaining
    booking1 = BookingFactory(performance=perf_1)
    TicketFactory(booking=booking1, seat_group=seat_group_small)

    # check bookings with performance capacity limit
    booking2 = BookingFactory(performance=perf_2)
    TicketFactory(booking=booking2, seat_group=seat_group_all)
    TicketFactory(booking=booking2, seat_group=seat_group_best)

    request = (
        """
        query {
            production(slug: "%s") {
                totalCapacity
                performances{
                    edges{
                        node{
                            capacity
                            capacityRemaining
                            ticketsBreakdown{
                                totalCapacity
                            }
                            ticketOptions{
                                capacity
                                capacityRemaining
                            }
                            venue{
                                internalCapacity
                            }
                        }
                    }
                }
            }
        }
    """
        % production.slug
    )

    response = gql_client.execute(request)

    assert response["data"]["production"] == {
        "totalCapacity": venue_capacity + performance_limit_capacity + 170,
        "performances": {
            "edges": [
                {
                    "node": {
                        "capacity": None,
                        "capacityRemaining": venue_capacity - 1,
                        "ticketsBreakdown": {"totalCapacity": venue_capacity},
                        "ticketOptions": [
                            {
                                "capacity": sg_all_capacity,
                                "capacityRemaining": sg_all_capacity - 1,
                            },
                            {
                                "capacity": sg_small_capacity,
                                "capacityRemaining": sg_small_capacity - 1,
                            },
                            {
                                "capacity": sg_best_capacity - 10,
                                "capacityRemaining": sg_best_capacity - 10,
                            },
                        ],
                        "venue": {"internalCapacity": venue_capacity},
                    }
                },
                {
                    "node": {
                        "capacity": performance_limit_capacity,
                        "capacityRemaining": performance_limit_capacity - 2,
                        "ticketsBreakdown": {
                            "totalCapacity": performance_limit_capacity
                        },
                        "ticketOptions": [
                            {
                                "capacity": sg_all_capacity,
                                "capacityRemaining": performance_limit_capacity - 2,
                            },
                            {
                                "capacity": sg_small_capacity,
                                "capacityRemaining": sg_small_capacity,
                            },
                            {
                                "capacity": sg_best_capacity - 10,
                                "capacityRemaining": sg_best_capacity - 10 - 1,
                            },
                        ],
                        "venue": {"internalCapacity": venue_capacity},
                    }
                },
                {
                    "node": {
                        "capacity": performance_limit_capacity,
                        "capacityRemaining": psg_capacity,
                        "ticketsBreakdown": {"totalCapacity": psg_capacity},
                        "ticketOptions": [
                            {
                                "capacity": psg_capacity,
                                "capacityRemaining": psg_capacity,
                            },
                        ],
                        "venue": {"internalCapacity": venue_capacity},
                    }
                },
            ]
        },
    }
