"""
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
            seatGroup: "%(seat_group)s"
            price: 800
            capacity: 100
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
