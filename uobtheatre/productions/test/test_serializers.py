import pytest

from uobtheatre.productions.test.factories import (
    ProductionFactory,
    SocietyFactory,
    VenueFactory,
    PerformanceFactory,
    CrewMemberFactory,
    CastMemberFactory,
)
from uobtheatre.productions.serializers import (
    ProductionSerializer,
    SocietySerializer,
    VenueSerializer,
    PerformanceSerializer,
    CrewMemberSerialzier,
    CastMemberSerialzier,
)
from uobtheatre.productions.models import (
    Production,
    Performance,
    Society,
    Venue,
    CrewRole,
    CrewMember,
    CastMember,
)


@pytest.mark.django_db
def test_society_serializer():
    society = SocietyFactory()
    data = Society.objects.first()
    serialized_society = SocietySerializer(data)

    assert serialized_society.data == {
        "id": society.id,
        "name": society.name,
    }


@pytest.mark.django_db
def test_production_serializer():
    production = ProductionFactory()
    data = Production.objects.first()
    serialized_prod = ProductionSerializer(data)

    performances = [
        {
            "id": performance.id,
            "production": performance.production.id,
            "venue": {
                "id": performance.venue.id,
                "name": performance.venue.name,
            },
            "start": performance.start.isoformat() + "+0000",
            "end": performance.end.isoformat() + "+0000",
        }
        for performance in production.performances.all()
    ]

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

    assert serialized_prod.data == {
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
        "performances": performances,
        "warnings": warnings,
        "cast": cast,
        "crew": crew,
    }


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
