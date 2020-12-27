import math

import pytest
from django.template.defaultfilters import slugify

from uobtheatre.bookings.test.factories import (
    DiscountFactory,
    DiscountRequirementFactory,
    PerformanceSeatingFactory,
)
from uobtheatre.productions.models import (
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    Production,
    Venue,
)
from uobtheatre.productions.serializers import (
    CastMemberSerialzier,
    CrewMemberSerialzier,
    PerformanceSerializer,
    PerformanceTicketTypesSerializer,
    ProductionSerializer,
    VenueSerializer,
)
from uobtheatre.productions.test.factories import (
    CastMemberFactory,
    CrewMemberFactory,
    PerformanceFactory,
    ProductionFactory,
    VenueFactory,
)
from uobtheatre.venues.test.factories import SeatGroupFactory


@pytest.mark.django_db
def test_production_serializer(date_format):
    production = ProductionFactory()
    data = Production.objects.first()
    serialized_prod = ProductionSerializer(data)

    warnings = [warning.name for warning in production.warnings.all()]

    cast = [
        {
            "name": castmember.name,
            "profile_picture": castmember.profile_picture.url,
            "role": castmember.role,
        }
        for castmember in production.cast.all()
    ]

    crew = [
        {
            "name": crewmember.name,
            "role": crewmember.role.name,
        }
        for crewmember in production.crew.all()
    ]

    expected_output = {
        "id": production.id,
        "name": production.name,
        "subtitle": production.subtitle,
        "description": production.description,
        "society": {
            "id": production.society.id,
            "name": production.society.name,
            "logo": production.society.logo.url if production.society.logo else None,
        },
        "poster_image": production.poster_image.url,
        "featured_image": production.featured_image.url,
        "cover_image": production.cover_image.url,
        "age_rating": production.age_rating,
        "facebook_event": production.facebook_event,
        "warnings": warnings,
        "cast": cast,
        "crew": crew,
        "performances": [],
        "start_date": None,
        "end_date": None,
        "slug": production.slug,
    }
    assert expected_output == serialized_prod.data

    # Add 2 performances
    PerformanceFactory(production=production)
    PerformanceFactory(production=production)
    performances = [
        {
            "id": performance.id,
            "production_id": performance.production.id,
            "venue": {
                "id": performance.venue.id,
                "name": performance.venue.name,
            },
            "extra_information": performance.extra_information,
            "start": performance.start.strftime(date_format),
            "end": performance.end.strftime(date_format),
        }
        for performance in production.performances.all()
    ]
    assert len(performances) == 2

    performance_updates = {
        "performances": performances,
        "start_date": production.start_date().strftime(date_format),
        "end_date": production.end_date().strftime(date_format),
        "slug": production.slug,
    }
    expected_output.update(performance_updates)

    serialized_prod = ProductionSerializer(data)
    assert expected_output == serialized_prod.data


@pytest.mark.django_db
def test_performance_serializer(date_format):
    performance = PerformanceFactory()
    data = Performance.objects.first()
    serialized_performance = PerformanceSerializer(data)

    assert serialized_performance.data == {
        "id": performance.id,
        "production_id": performance.production.id,
        "venue": {
            "id": performance.venue.id,
            "name": performance.venue.name,
        },
        "extra_information": performance.extra_information,
        "start": performance.start.strftime(date_format),
        "end": performance.end.strftime(date_format),
    }


@pytest.mark.django_db
def test_crew_member_serializer():
    crew_member = CrewMemberFactory()
    data = CrewMember.objects.first()
    serialized_crew_member = CrewMemberSerialzier(data)

    assert serialized_crew_member.data == {
        "name": crew_member.name,
        "role": crew_member.role.name,
    }


@pytest.mark.django_db
def test_cast_member_serializer():
    cast_member = CastMemberFactory()
    data = CastMember.objects.first()
    serialized_cast_member = CastMemberSerialzier(data)

    assert serialized_cast_member.data == {
        "name": cast_member.name,
        "role": cast_member.role,
        "profile_picture": cast_member.profile_picture.url,
    }


@pytest.mark.django_db
def test_performance_ticket_types_serializer():
    performance = PerformanceFactory()

    # Create some seat groups for this performance
    performance_seat_group_1 = PerformanceSeatingFactory(performance=performance)
    performance_seat_group_2 = PerformanceSeatingFactory(performance=performance)

    # Create a discount
    discount_1 = DiscountFactory(name="Family", discount=0.2)
    discount_1.performances.set([performance])
    discount_requirement_1 = DiscountRequirementFactory(discount=discount_1, number=1)

    # Create a different
    discount_2 = DiscountFactory(name="Family 2", discount=0.3)
    discount_2.performances.set([performance])
    discount_requirement_2 = DiscountRequirementFactory(discount=discount_2, number=1)

    serialized_ticket_types = PerformanceTicketTypesSerializer(performance)

    assert serialized_ticket_types.data == {
        "ticket_types": [
            {
                "seat_group": {
                    "name": performance_seat_group_1.seat_group.name,
                    "id": performance_seat_group_1.seat_group.id,
                },
                "concession_types": [
                    {
                        "concession": {
                            "name": discount_requirement_1.concession_type.name,
                            "id": discount_requirement_1.concession_type.id,
                        },
                        "price": math.ceil(0.8 * performance_seat_group_1.price),
                        "price_pounds": "%.2f"
                        % (math.ceil(0.8 * performance_seat_group_1.price) / 100),
                    },
                    {
                        "concession": {
                            "name": discount_requirement_2.concession_type.name,
                            "id": discount_requirement_2.concession_type.id,
                        },
                        "price": math.ceil(0.7 * performance_seat_group_1.price),
                        "price_pounds": "%.2f"
                        % (math.ceil(0.7 * performance_seat_group_1.price) / 100),
                    },
                ],
            },
            {
                "seat_group": {
                    "name": performance_seat_group_2.seat_group.name,
                    "id": performance_seat_group_2.seat_group.id,
                },
                "concession_types": [
                    {
                        "concession": {
                            "name": discount_requirement_1.concession_type.name,
                            "id": discount_requirement_1.concession_type.id,
                        },
                        "price": math.ceil(0.8 * performance_seat_group_2.price),
                        "price_pounds": "%.2f"
                        % (math.ceil(0.8 * performance_seat_group_2.price) / 100),
                    },
                    {
                        "concession": {
                            "name": discount_requirement_2.concession_type.name,
                            "id": discount_requirement_2.concession_type.id,
                        },
                        "price": math.ceil(0.7 * performance_seat_group_2.price),
                        "price_pounds": "%.2f"
                        % (math.ceil(0.7 * performance_seat_group_2.price) / 100),
                    },
                ],
            },
        ],
    }
