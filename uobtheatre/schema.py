"""
Defines base schema for api
"""


import graphene

import uobtheatre.bookings.schema as bookings_schema
import uobtheatre.discounts.schema as discounts_schema
import uobtheatre.payments.mutations as payments_mutations
import uobtheatre.payments.schema as payments_schema
import uobtheatre.productions.schema as productions_schema
import uobtheatre.productions.mutations as productions_mutations
import uobtheatre.reports.schema as reports_schema
import uobtheatre.societies.schema as societies_schema
import uobtheatre.users.schema as users_schema
import uobtheatre.venues.schema as venues_schema
import uobtheatre.images.schema as image_schema


class Query(
    venues_schema.Query,
    productions_schema.Query,
    societies_schema.Query,
    users_schema.Query,
    bookings_schema.Query,
    payments_schema.Query,
    image_schema.Query,
    graphene.ObjectType,
):
    """
    Defines base Query for api
    """


class Mutation(
    users_schema.Mutation,
    bookings_schema.Mutation,
    reports_schema.Mutation,
    payments_mutations.Mutation,
    productions_mutations.Mutation,
    discounts_schema.Mutation,
    graphene.ObjectType,
):
    """
    Defines base Mutation for api
    """


schema = graphene.Schema(query=Query, mutation=Mutation)
