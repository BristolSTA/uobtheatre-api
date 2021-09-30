import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.productions.models import Production
from uobtheatre.societies.test.factories import SocietyFactory
from uobtheatre.venues.test.factories import SeatGroupFactory, VenueFactory

full_query = """
mutation {
  createProduction(
    name: "Legally Ginger"
    subtitle: "A show about things"
    societyId: "%(society_id)s"
    ageRating: 10
    facebookEvent: "www.facebookevent.com"
    warnings: [
      {
        description: "scary stuff"
      }
    ]
    cast: [
      {
        name: "Alex",
        role: "Peter",
      }
    ]
    crew: [
      {
        name: "Tom"
        role: {
          name: "Noise"
          department: SND
        }
      }
    ]
    productionTeam: [
      {
        name: "James"
        role: "Director"
      }
    ]
    coverImageId: "%(cover_image_id)s"
    featuredImageId: "%(featured_image_id)s"
    posterImageId: "%(poster_image_id)s"
    performances: [
      {
        venueId: "%(venue_id)s"
        doorsOpen: "2021-09-19T20:44:00.739149"
        start: "2021-09-19T20:44:00.739149"
        end: "2021-09-19T20:44:00.739149"
        description:"Matinee things"
        extraInformation: "Blah blah"
        ticketOptions: [
          {
            seatGroup: "%(seat_group_id)s"
            price: 800
            capacity: 100
          }
        ]
        discounts: [
          {
            discountValue: 0.2
            requirements: {
                concessionId: "id"
                number: 1
            }
          }
        ]
      }
    ]
  ) {
    production {
      id
      facebookEvent
      society {
        id
        name
      }
      warnings {
        id
        description
      }
      cast {
        id
        name
        role
      }
      crew {
        name
        role {
          id
          department {
            value
            description
          }
          name
        }
      }
      coverImage {
        id
        url
      }
      performances {
        edges {
          node {
            id
          }
        }
      }
    }
  }
}
"""


@pytest.mark.django_db
def test_create_production(gql_client):
    society = SocietyFactory()

    cover_image = ImageFactory()
    poster_image = ImageFactory()
    feature_image = ImageFactory()

    venue = VenueFactory()

    seat_group = SeatGroupFactory()

    gql_client.execute(
        full_query
        % {
            "society_id": to_global_id("SocietyNode", society.id),
            "cover_image_id": to_global_id("ImageNode", cover_image.id),
            "featured_image_id": to_global_id("ImageNode", feature_image.id),
            "poster_image_id": to_global_id("ImageNode", poster_image.id),
            "venue_id": to_global_id("VenueNode", venue.id),
            "seat_group_id": to_global_id("SeatGroupNode", seat_group.id),
        }
    )

    assert Production.objects.count() == 1

    production = Production.objects.first()
    assert production.name == "Legally Ginger"
    assert production.subtitle == "A show about things"
    assert production.age_rating == 10
    assert production.facebook_event == "www.facebookevent.com"

    assert production.society == society

    assert production.warnings.count() == 1
    assert production.warnings.first().description == "scary stuff"

    assert production.cast.count() == 1
    assert production.crew.count() == 1
    assert production.production_team.count() == 1

    assert production.performnaces.count() == 1
