import django_filters
import graphene
from graphene_django.filter import GlobalIDFilter
from graphql.language.ast import IntValue, StringValue
from graphql_relay.node.node import from_global_id

from uobtheatre.utils.exceptions import AuthException, SafeMutation


class GrapheneImageField(graphene.Field):
    pass


class GrapheneImageFieldNode(graphene.ObjectType):
    url = graphene.String(required=True)
    name = graphene.String()


def generate_resolver(field_name):
    def resolver(self, info):
        if not getattr(self, field_name) or not hasattr(
            getattr(self, field_name), "url"
        ):
            return None
        return getattr(self, field_name)

    return resolver


class GrapheneImageMixin:
    """
    Adds image support to graphene.Field
    """

    @classmethod
    def __init_subclass_with_meta__(self, *args, **kwargs):
        """
        Overwrite the DjangoObjectType init to add in resolvers for every
        GrapheneImageField.
        """

        # Do the regular init
        super().__init_subclass_with_meta__(*args, **kwargs)

        # For every GrapheneImageField add a resolver
        for name, type in self._meta.fields.items():
            if isinstance(type, GrapheneImageField):
                setattr(self, f"resolve_{name}", generate_resolver(name))


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


class FilterSet(django_filters.FilterSet):
    id = GlobalIDFilter()
