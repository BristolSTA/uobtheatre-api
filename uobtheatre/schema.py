import graphene

import uobtheatre.venues.schema as venues_schema


class Query(venues_schema.Query, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query)
