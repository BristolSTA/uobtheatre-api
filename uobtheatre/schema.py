import graphene

import uobtheatre.productions.schema as productions_schema
import uobtheatre.societies.schema as societies_schema
import uobtheatre.users.schema as users_schema
import uobtheatre.venues.schema as venues_schema


class Query(
    venues_schema.Query,
    productions_schema.Query,
    societies_schema.Query,
    users_schema.Query,
    graphene.ObjectType,
):
    pass


schema = graphene.Schema(query=Query)
