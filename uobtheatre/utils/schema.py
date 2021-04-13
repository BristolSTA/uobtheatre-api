import graphene
from graphene_django import DjangoObjectType
from graphql.language.ast import IntValue, StringValue
from graphql_relay.node.node import from_global_id

from uobtheatre.utils.enums import GrapheneEnumMixin
from uobtheatre.utils.exceptions import AuthException, SafeMutation


class CustomDjangoObjectType(GrapheneEnumMixin, DjangoObjectType):
    class Meta:
        abstract = True


class AuthRequiredMixin(SafeMutation):
    """
    Before the mutation occurs, it is checked the user is authenticated. If not
    an error reponse is returned.
    """

    @classmethod
    def mutate(cls, root, info, **inputs):
        if not info.context.user.is_authenticated:
            exception = AuthException()
            return cls(errors=exception.resolve(), success=False)

        return super().mutate(root, info, **inputs)


class IdInputField(graphene.ID):
    """
    An input field for global IDs. When parsed the value is converted to an
    int.
    """

    @staticmethod
    def parse_literal(global_id):
        if isinstance(global_id, (StringValue, IntValue)):
            return from_global_id(global_id.value)[1]

    @staticmethod
    def parse_value(ast):
        return from_global_id(ast)[1]
