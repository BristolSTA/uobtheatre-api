import pytest

from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory


@pytest.mark.django_db
def test_productions_schema(gql_client):

    production = ProductionFactory()
    performances = [PerformanceFactory(production=production) for i in range(2)]

    response = gql_client.execute(
        """
        {
	  productions {
            ageRating
            coverImage
            description
            facebookEvent
            featuredImage
            id
            name
            posterImage
            slug
            subtitle
            performances {
              id
            }
          }
        }
        """
    )

    assert response == {
        "data": {
            "productions": [
                {
                    "ageRating": production.age_rating,
                    "coverImage": production.cover_image,
                    "description": production.description,
                    "facebookEvent": production.facebook_event,
                    "featuredImage": production.featured_image,
                    "id": str(production.id),
                    "name": production.name,
                    "posterImage": production.poster_image,
                    "slug": production.slug,
                    "subtitle": production.subtitle,
                    "performances": [
                        {"id": str(performance.id)} for performance in performances
                    ],
                }
            ]
        }
    }


@pytest.mark.django_db
def test_production_by_id(gql_client):
    production = ProductionFactory()

    query_string = "{ productions(id: %s) { id } }"

    response = gql_client.execute(query_string % (production.id + 1))
    assert response["data"] == {"productions": []}

    response = gql_client.execute(query_string % (production.id))
    assert response["data"] == {"productions": [{"id": str(production.id)}]}


@pytest.mark.django_db
def test_performance_schema(gql_client):
    performances = [PerformanceFactory() for i in range(1)]

    response = gql_client.execute(
        """
        {
	  performances {
            capacity
            doorsOpen
            end
            extraInformation
            id
            production {
              id
            }
            start
            capacityRemaining
          }
        }
        """
    )

    assert response == {
        "data": {
            "performances": [
                {
                    "capacity": performance.capacity,
                    "doorsOpen": performance.doors_open.isoformat(),
                    "end": performance.end.isoformat(),
                    "extraInformation": performance.extra_information,
                    "id": str(performance.id),
                    "production": {"id": str(performance.production.id)},
                    "start": performance.start.isoformat(),
                    "capacityRemaining": performance.capacity_remaining(),
                }
                for performance in performances
            ]
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "attribute, is_obj",
    [
        ("bookings", True),
    ],
)
def test_performance_blocked_attributes(gql_client, attribute, is_obj):
    query_string = """
        {
            performances {
                %s
            }
        }
        """ % (
        attribute if not is_obj else "%s {id}" % attribute
    )

    response = gql_client.execute(query_string)
    assert (
        response["errors"][0]["message"]
        == f'Cannot query field "{attribute}" on type "PerformanceType".'
    )
