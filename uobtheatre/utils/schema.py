import django_filters
import graphene
from graphene_django.filter import GlobalIDFilter
from graphql.language.ast import IntValue, StringValue
from graphql_relay.node.node import from_global_id

from uobtheatre.utils.exceptions import AuthException, SafeMutation


class EnumNode(graphene.ObjectType):
    value = graphene.String()
    description = graphene.String()


class GrapheneEnumMixin:
    """
    Adds image support to graphene.Field
    """

    def _generate_enum_resolver(field_name):
        def resolver(cls, info):
            return EnumNode(
                value=getattr(cls, field_name),
                description=getattr(cls, f"get_{field_name}_display")(),
            )

        return resolver

    @classmethod
    def __init_subclass_with_meta__(self, *args, **kwargs):
        """
        Overwrite the DjangoObjectType init to add in resolvers for every
        GrapheneImageField.
        """

        # Do the regular init
        super().__init_subclass_with_meta__(*args, **kwargs)

        # For every EnumNode add a resolver
        for name, field_type in self._meta.fields.items():
            if hasattr(field_type, "type"):
                if field_type.type == EnumNode:
                    print(f"{name} is an EnumNode")
                    setattr(self, f"resolve_{name}", self._generate_enum_resolver(name))


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


class FilterSet(django_filters.FilterSet):
    id = GlobalIDFilter()
