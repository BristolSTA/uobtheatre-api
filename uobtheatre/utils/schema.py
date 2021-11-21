from typing import List
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

import graphene
from django.db.models import RestrictedError
from django.forms.models import ModelChoiceField
from graphene.types.mutation import MutationOptions
from graphene_django import DjangoObjectType
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphql.language.ast import IntValue, StringValue
from graphql_relay.node.node import from_global_id
from guardian.shortcuts import get_users_with_perms

from uobtheatre.users.schema import ExtendedUserNode
from uobtheatre.users.abilities import Ability
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


class AuthRequiredMixin:
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


class PermissionNode(graphene.ObjectType):
    name = graphene.String()
    description = graphene.String()


class UserPermissionsNode(graphene.ObjectType):
    user = graphene.Field(ExtendedUserNode)
    assigned_permissions = graphene.List(graphene.String)


class AssignedUsersMixin:
    """Adds schema objects to show assigned users as well as availble permissions. Authorisation is based on the object level change permission"""

    staff = graphene.List(UserPermissionsNode)
    available_staff_permissions = graphene.List(PermissionNode)

    class PermissionsMeta:
        schema_assignable_permissions = ()

    def __init__(self, *args, **kwargs) -> None:
        self._permissions_meta = self.PermissionsMeta()
        super().__init__(*args, **kwargs)

    def resolve_staff(self, info):
        if not info.context.user.has_perm("change_" + self._meta.model_name, self):
            return None

        return [
            UserPermissionsNode(
                user=user,
                assigned_permissions=permissions,
            )
            for (user, permissions) in get_users_with_perms(self, True).items()
        ]

    def resolve_available_staff_permissions(self, info):
        if not info.context.user.has_perm("change_" + self._meta.model_name, self):
            return None
        # TODO: Implement meta to only show certain permissions, and permissions to attach permissions
        available_perms = Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(self)
        ).all()
        return [
            PermissionNode(name=permission.codename, description=permission.name)
            for permission in available_perms
        ]


class SafeFormMutation(MutationResult, DjangoModelFormMutation):
    """Provides a wrapper around the DjangoModelFormMutation for use with out validation and authorization system"""

    class Meta:
        abstract = True

    @classmethod
    # pylint: disable=C0116
    def __init_subclass_with_meta__(
        cls, *args, create_ability=None, update_ability=None, **kwargs
    ) -> None:
        cls.is_creation = True
        cls.create_ability = create_ability
        cls.update_ability = update_ability
        super().__init_subclass_with_meta__(*args, **kwargs)

    @classmethod
    # pylint: disable=W0212
    def authorize_request(cls, root, info, **mInput):
        """Authorize the request (pre-validation)"""
        model_name = cls._meta.model._meta.model_name
        app_label = cls._meta.model._meta.app_label
        update_ability: Ability = cls.update_ability
        create_ability: Ability = cls.create_ability

        if not cls.is_creation:
            instance = cls.get_object_instance(root, info, **mInput)
            return (
                info.context.user.has_perm("change_%s" % model_name, instance)
                if not update_ability
                else update_ability.user_has(info.context.user, instance)
            )
        return (
            info.context.user.has_perm("%s.add_%s" % (app_label, model_name))
            if not create_ability
            else create_ability.user_has(info.context.user, None)
        )

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
        except KeyError:  # pragma: no cover
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
            if (
                isinstance(field, ModelChoiceField) and form[key].value()
            ):  # pragma: no cover
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
    ability = None


class ModelDeletionMutation(AuthRequiredMixin, SafeMutation):
    """Generic model deletion mutation. Simply set the model in meta and you are away!"""

    class Meta:
        abstract = True

    class Arguments:
        id = IdInputField()

    @classmethod
    def __init_subclass_with_meta__(
        cls, *args, model=None, ability=None, **options
    ):  # pragma: no cover
        """Inits the subclass with meta..."""
        if not model:
            raise Exception("model is required for ModelDeletionMutation")

        _meta = ModelDeletionMutationOptions(cls)
        _meta.model = model
        _meta.ability = ability

        super().__init_subclass_with_meta__(_meta=_meta, *args, **options)

    @classmethod
    def get_instance(cls, model_id: int):
        return cls._meta.model.objects.get(id=model_id)

    @classmethod
    # pylint: disable=W0212
    def authorize_request(cls, _, info, id: int):
        """Authorize the request"""
        instance = cls.get_instance(id)
        if cls._meta.ability:
            return cls._meta.ability.user_has(info.context.user, instance)

        if not info.context.user.has_perm(
            "delete_%s" % cls._meta.model._meta.model_name, instance
        ):
            raise AuthorizationException
        return True

    @classmethod
    # pylint: disable=C0103,W0622
    def resolve_mutation(
        cls,
        root,
        info,
        id: int,
    ):
        model_instance = cls.get_instance(id)

        try:
            model_instance.delete()
        except RestrictedError as error:
            raise ReferencedException() from error

        return ModelDeletionMutation()
