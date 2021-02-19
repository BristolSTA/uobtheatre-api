import graphene

import uobtheatre.productions.schema as productions_schema
import uobtheatre.societies.schema as societies_schema
import uobtheatre.users.schema as users_schema
import uobtheatre.venues.schema as venues_schema
from uobtheatre.utils.exceptions import FieldError, MutationResult


class Query(
    venues_schema.Query,
    productions_schema.Query,
    societies_schema.Query,
    users_schema.Query,
    graphene.ObjectType,
):
    pass


class CreateBooking(MutationResult, graphene.Mutation):

    some_output = graphene.String()

    class Arguments:
        input = graphene.String()

    @classmethod
    def mutate(self, root, info, input):
        return self(
            some_output=input,
            success=True,
            errors=[FieldError("Uhoh there is an error", code=400, field="booking")],
        )
        # raise GQLFieldError("Uhoh there is an error", code=400, field="booking")


class BookingMutation(graphene.ObjectType):
    create_booking = CreateBooking.Field()


class Mutation(BookingMutation, users_schema.Mutation, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
