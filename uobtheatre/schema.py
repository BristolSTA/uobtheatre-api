"""
Defines base schema for api
"""

import traceback

import graphene

import uobtheatre.bookings.schema as bookings_schema
import uobtheatre.images.schema as images_schema
import uobtheatre.payments.schema as payments_schema
import uobtheatre.productions.mutations as productions_mutations
import uobtheatre.productions.schema as productions_schema
import uobtheatre.societies.schema as societies_schema
import uobtheatre.users.schema as users_schema
import uobtheatre.venues.schema as venues_schema


class ExceptionMiddleware(object):
    def on_error(self, exc):
        traceback.print_tb(exc.__traceback__)
        raise exc

    def resolve(self, next, root, info, **kwargs):
        return next(root, info, **kwargs).catch(self.on_error)


class Query(
    venues_schema.Query,
    productions_schema.Query,
    societies_schema.Query,
    users_schema.Query,
    images_schema.Query,
    bookings_schema.Query,
    payments_schema.Query,
    graphene.ObjectType,
):
    """
    Defines base Query for api
    """


class Mutation(
    users_schema.Mutation,
    bookings_schema.Mutation,
    productions_mutations.Mutation,
    graphene.ObjectType,
):
    """
    Defines base Mutation for api
    """


schema = graphene.Schema(query=Query, mutation=Mutation)
