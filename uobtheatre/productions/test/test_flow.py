import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm

from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.productions.models import Performance
from uobtheatre.societies.test.factories import SocietyFactory
from uobtheatre.venues.test.factories import VenueFactory


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
