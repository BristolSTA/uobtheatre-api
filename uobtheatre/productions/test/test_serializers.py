import pytest

from uobtheatre.productions.test.factories import (
    ProductionFactory,
    VenueFactory,
    PerformanceFactory,
    CrewMemberFactory,
    CastMemberFactory,
)
from uobtheatre.productions.serializers import (
    ProductionSerializer,
    VenueSerializer,
    PerformanceSerializer,
    CrewMemberSerialzier,
    CastMemberSerialzier,
)
from uobtheatre.productions.models import (
    Production,
    Performance,
    Venue,
    CrewRole,
    CrewMember,
    CastMember,
)


DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@pytest.mark.django_db
def test_production_serializer():
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
    }
    assert expected_output == serialized_prod.data

    # Add 2 performances
    PerformanceFactory(production=production)
    PerformanceFactory(production=production)
    performances = [
        {
            "id": performance.id,
            "production": performance.production.id,
            "venue": {
                "id": performance.venue.id,
                "name": performance.venue.name,
            },
            "extra_information": performance.extra_information,
            "start": performance.start.isoformat()[:-3] + "00",
            "end": performance.end.isoformat()[:-3] + "00",
        }
        for performance in production.performances.all()
    ]
    assert len(performances) == 2

    performance_updates = {
        "performances": performances,
        "start_date": production.start_date().strftime(DATE_FORMAT),
        "end_date": production.end_date().strftime(DATE_FORMAT),
    }
    expected_output.update(performance_updates)

    serialized_prod = ProductionSerializer(data)
    assert expected_output == serialized_prod.data


@pytest.mark.django_db
def test_venue_serializer():
    venue = VenueFactory()
    data = Venue.objects.first()
    serialized_venue = VenueSerializer(data)

    assert serialized_venue.data == {
        "id": venue.id,
        "name": venue.name,
    }


@pytest.mark.django_db
def test_performance_serializer():
    performance = PerformanceFactory()
    data = Performance.objects.first()
    serialized_performance = PerformanceSerializer(data)

    assert serialized_performance.data == {
        "id": performance.id,
        "production": performance.production.id,
        "venue": {
            "id": performance.venue.id,
            "name": performance.venue.name,
        },
        "extra_information": performance.extra_information,
        "start": performance.start.isoformat() + "+0000",
        "end": performance.end.isoformat() + "+0000",
    }


@pytest.mark.django_db
def test_crew_member_serializer():
    crew_member = CrewMemberFactory()
    data = CrewMember.objects.first()
    serialized_crew_member = CrewMemberSerialzier(data)

    assert serialized_crew_member.data == {
        "id": crew_member.id,
        "name": crew_member.name,
        "role": crew_member.role.name,
    }


@pytest.mark.django_db
def test_cast_member_serializer():
    cast_member = CastMemberFactory()
    data = CastMember.objects.first()
    serialized_cast_member = CastMemberSerialzier(data)

    assert serialized_cast_member.data == {
        "id": cast_member.id,
        "name": cast_member.name,
        "role": cast_member.role,
        "profile_picture": cast_member.profile_picture.url,
    }
