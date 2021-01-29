import graphene

import uobtheatre.bookings.schema
import uobtheatre.productions.schema
import uobtheatre.societies.schema
import uobtheatre.venues.schema


class Query(
    uobtheatre.venues.schema.Query,
    uobtheatre.productions.schema.Query,
    uobtheatre.bookings.schema.Query,
    uobtheatre.societies.schema.Query,
    graphene.ObjectType,
):
    pass


class Mutation(uobtheatre.bookings.schema.Mutation, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
