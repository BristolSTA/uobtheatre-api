from typing import List

import graphene
from django.db.models import RestrictedError
from django.forms.models import ModelChoiceField
from graphene.types.mutation import MutationOptions
from graphene_django import DjangoObjectType
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphql.language.ast import IntValue, StringValue
from graphql_relay.node.node import from_global_id

from uobtheatre.utils.enums import GrapheneEnumMixin
from uobtheatre.utils.exceptions import (
    AuthException,
    AuthorizationException,
    GQLException,
    GQLExceptions,
    MutationException,
    MutationResult,
    ReferencedException,
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
    """Provides a wrapper around the DjangoModelFormMutation for use with out validation and authorization system"""

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, *args, **kwargs) -> None:
        cls.is_creation = True
        super().__init_subclass_with_meta__(*args, **kwargs)

    @classmethod
    # pylint: disable=W0212
    def authorize_request(cls, root, info, **mInput):
        """Authorize the request (pre-validation)"""
        model_name = cls._meta.model._meta.model_name
        app_label = cls._meta.model._meta.app_label
        if not cls.is_creation:
            instance = cls.get_object_instance(root, info, **mInput)
            return info.context.user.has_perm("change_%s" % model_name, instance)
        return info.context.user.has_perm("%s.add_%s" % (app_label, model_name))

    @classmethod
    def on_success(cls, info, response, is_creation):
        """Callback method run when the save is successful"""

    @classmethod
    def on_creation(cls, info, response):
        """Callback method run when a creation save is successful"""

    @classmethod
    def on_update(cls, info, response):
        """Callback method run when a update save is successful"""

    @classmethod
    def get_object_instance(cls, root, info, **mInput):
        """Get the subject object's instance (if exists)"""
        kwargs = cls.get_form_kwargs(root, info, **mInput)

        try:
            return kwargs["instance"]
        except KeyError:
            return None

    @classmethod
    def get_field(cls, root, info, key, **mInput):
        return cls.get_form(root, info, **mInput)[key].field

    @classmethod
    def get_python_value(cls, root, info, key, **mInput):
        return cls.get_field(root, info, key, **mInput).to_python(
            cls.get_key_raw_value(root, info, key, **mInput)
        )

    @classmethod
    def get_key_raw_value(cls, root, info, key, **mInput):
        return cls.get_form(root, info, **mInput)[key].value()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **mInput):
        """Mutate and get payload override"""
        if "id" in mInput:
            mInput["id"] = from_global_id(mInput["id"])[1]
            cls.is_creation = False
        else:
            cls.is_creation = True

        # Fix for relay. Will convert any Django model input / choice fields from global IDs to local
        form = cls.get_form(root, info, **mInput)
        for (key, field) in form.fields.items():
            if isinstance(field, ModelChoiceField) and form[key].value():
                try:
                    if isinstance(form[key].value(), List):
                        mInput[key] = [from_global_id(item)[1] for item in mInput[key]]
                    else:
                        mInput[key] = from_global_id(form[key].value())[1]
                except TypeError:
                    pass

        # Authorize
        try:
            if not cls.authorize_request(root, info, **mInput):
                raise AuthorizationException

        except MutationException as exception:
            # These are our custom exceptions
            return cls(errors=exception.resolve(), success=False)

        response = super().mutate_and_get_payload(root, info, **mInput)

        if len(response.errors):
            exceptions = GQLExceptions(
                exceptions=[
                    GQLException(message, field=error.field)
                    for error in response.errors
                    for message in error.messages
                ]
            )
            return cls(errors=exceptions.resolve(), success=False)

        cls.on_success(info, response, cls.is_creation)
        if cls.is_creation:
            cls.on_creation(info, response)
        else:
            cls.on_update(info, response)

        return response


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


class ModelDeletionMutationOptions(MutationOptions):
    model = None


class ModelDeletionMutation(AuthRequiredMixin):
    """Generic model deletion mutation. Simply set the model in meta and you are away!"""

    class Meta:
        abstract = True

    class Arguments:
        id = IdInputField()

    @classmethod
    def __init_subclass_with_meta__(cls, *args, model=None, **options):
        """Inits the subclass with meta..."""
        if not model:
            raise Exception("model is required for ModelDeletionMutation")

        _meta = ModelDeletionMutationOptions(cls)
        _meta.model = model

        super().__init_subclass_with_meta__(_meta=_meta, *args, **options)

    @classmethod
    # pylint: disable=W0212
    def authorize_request(cls, info, instance):
        """Authorize the request"""
        if not info.context.user.has_perm(
            "delete_%s" % cls._meta.model._meta.model_name, instance
        ):
            raise AuthorizationException

    @classmethod
    # pylint: disable=C0103,W0622
    def resolve_mutation(
        cls,
        _,
        info,
        id: int,
    ):
        model_instance = cls._meta.model.objects.get(id=id)

        # Authorise
        cls.authorize_request(info, model_instance)

        try:
            model_instance.delete()
        except RestrictedError as error:
            raise ReferencedException() from error

        return ModelDeletionMutation()
