"""
Defines base schema for api
"""

import graphene

import uobtheatre.bookings.schema as bookings_schema
import uobtheatre.productions.schema as productions_schema
import uobtheatre.societies.schema as societies_schema
import uobtheatre.users.schema as users_schema
import uobtheatre.venues.schema as venues_schema


class Query(
    venues_schema.Query,
    productions_schema.Query,
    societies_schema.Query,
    users_schema.Query,
    bookings_schema.Query,
    graphene.ObjectType,
):
    """
    Defines base Query for api
    """


class Mutation(users_schema.Mutation, bookings_schema.Mutation, graphene.ObjectType):
    """
    Defines base Mutation for api
    """


schema = graphene.Schema(query=Query, mutation=Mutation)
