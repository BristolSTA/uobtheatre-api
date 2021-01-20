import graphene

import uobtheatre.bookings.schema as bookings_schema
import uobtheatre.productions.schema as productions_schema
import uobtheatre.venues.schema as venues_schema


class Query(
    venues_schema.Query,
    productions_schema.Query,
    bookings_schema.Query,
    graphene.ObjectType,
):
    pass


schema = graphene.Schema(query=Query)
