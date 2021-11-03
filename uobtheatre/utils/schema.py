from typing import List
from django.forms.models import (
    ModelChoiceField,
    model_to_dict,
)
import graphene
from graphene_django import DjangoObjectType
from graphene_django.forms.mutation import (
    DjangoModelFormMutation,
)
from graphql.language.ast import IntValue, StringValue
from graphql_relay.node.node import from_global_id

from uobtheatre.utils.enums import GrapheneEnumMixin
from uobtheatre.utils.exceptions import (
    AuthException,
    GQLException,
    GQLExceptions,
    MutationException,
    MutationResult,
    SafeMutation,
)


class CustomDjangoObjectType(GrapheneEnumMixin, DjangoObjectType):
    class Meta:
        abstract = True


class AuthRequiredMixin(SafeMutation):
    """Adds check to see if user is logged in before mutation

    At the start of mutate, checks if the user is authentacated (logged in to
    any user account). If not an error object is returned, otherwise the
    mutation function continues as normal.
    """

    @classmethod
    def mutate(cls, root, info, **inputs):
        """Check if user is authentacated before super mutate.
        Check if user is authentacated and returns error if not, otherwise runs
        super mutate function.
        """
        if not info.context.user.is_authenticated:
            exception = AuthException()
            return cls(errors=exception.resolve(), success=False)

        return super().mutate(root, info, **inputs)


class SafeFormMutation(MutationResult, DjangoModelFormMutation):
    class Meta:
        abstract = True

    @classmethod
    def authorize_request(cls, root, info, **input):
        return True

    @classmethod
    def on_success(cls, info, response):
        pass

    @classmethod
    def get_object_instance(cls, root, info, **input):
        kwargs = cls.get_form_kwargs(root, info, **input)

        try:
            return kwargs["instance"]
        except KeyError:
            return None

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        if "id" in input:
            input["id"] = from_global_id(input["id"])[1]

        # Authorize
        try:
            if not cls.authorize_request(root, info, **input):
                raise GQLException(message="Not authorized", code=401)

        except MutationException as exception:
            # These are our custom exceptions
            return cls(errors=exception.resolve(), success=False)

        # Fix for relay. Will convert any Django model input / choice fields from global IDs to local
        form = cls.get_form(root, info, **input)
        for (key, field) in form.fields.items():
            if isinstance(field, ModelChoiceField) and form[key].value():
                try:
                    if isinstance(form[key].value(), List):
                        input[key] = [from_global_id(item)[1] for item in input[key]]
                    else:
                        input[key] = from_global_id(form[key].value())[1]
                except TypeError:
                    pass

        response = super().mutate_and_get_payload(root, info, **input)

        if len(response.errors):
            exceptions = GQLExceptions(
                exceptions=[
                    GQLException(message, field=error.field)
                    for error in response.errors
                    for message in error.messages
                ]
            )
            return cls(errors=exceptions.resolve(), success=False)

        cls.on_success(info, response)
        return response

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        kwargs = super().get_form_kwargs(root, info, **input)
        endargs = {
            "data": {
                **(model_to_dict(kwargs["instance"]) if "instance" in kwargs else {}),
                **kwargs["data"],
            },
            "instance": kwargs["instance"] if "instance" in kwargs else None,
        }
        return endargs


class IdInputField(graphene.ID):
    """Input field used for global ID in mutation.

    When accepting a global id in a mutation (local ids should never be used)
    this Field should be used. The value received by the mutate function will
    then contain the local id (integer value).
    """

    @staticmethod
    def parse_literal(input_id):  # pylint: disable=W0221
        """Convert global id to local id.

        Given the global id provided in the mutation (directly as an argument)
        covert it to the local integer id.
        """
        if isinstance(input_id, (StringValue, IntValue)):
            return from_global_id(input_id.value)[1]
        return None

    @staticmethod
    def parse_value(ast):
        """Convert global id to local id.

        Given the global id provided in the mutation (as a gql variable) covert
        it to the local integer id.
        """
        return from_global_id(ast)[1]
