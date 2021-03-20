import django_filters
import graphene
from graphene_django.filter import GlobalIDFilter
from graphql.language.ast import IntValue, StringValue
from graphql_relay.node.node import from_global_id

from uobtheatre.utils.exceptions import AuthException, SafeMutation


class AuthRequiredMixin(SafeMutation):
    @classmethod
    def mutate(cls, root, info, **input):
        if not info.context.user.is_authenticated:
            exception = AuthException()
            return cls(errors=exception.resolve(), success=False)

        return super().mutate(root, info, **input)


class IdInputField(graphene.ID):
    @staticmethod
    def parse_literal(id):
        if isinstance(id, (StringValue, IntValue)):
            return from_global_id(id.value)[1]

    @staticmethod
    def parse_value(ast):
        return from_global_id(ast)[1]


class FilterSet(django_filters.FilterSet):
    id = GlobalIDFilter()
