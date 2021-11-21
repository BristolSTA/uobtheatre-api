from typing import List

import graphene
from django.db.models import RestrictedError
from django.forms.models import ModelChoiceField
from graphene.types.mutation import MutationOptions
from graphene_django import DjangoObjectType
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphql.language.ast import IntValue, StringValue
from graphql_relay.node.node import from_global_id
from guardian.shortcuts import (
    assign,
    assign_perm,
    get_user_perms,
    get_users_with_perms,
    remove_perm,
)

from uobtheatre.users.abilities import Ability
from uobtheatre.users.models import User
from uobtheatre.users.schema import ExtendedUserNode
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
from uobtheatre.utils.models import PermissionableModel


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


class PermissionNode(graphene.ObjectType):
    name = graphene.String()
    description = graphene.String()
    user_can_assign = graphene.Boolean(default_value=False)


class UserPermissionsNode(graphene.ObjectType):
    user = graphene.Field(ExtendedUserNode)
    assigned_permissions = graphene.List(graphene.String)


class AssignedUsersMixin:
    """Adds schema objects to show assigned users as well as availble permissions. Authorisation is based on the object level change permission"""

    assigned_users = graphene.List(UserPermissionsNode)
    assignable_permissions = graphene.List(PermissionNode)

    def resolve_assigned_users(self, info):
        if not info.context.user.has_perm("change_" + self._meta.model_name, self):
            return None

        return [
            UserPermissionsNode(
                user=user,
                assigned_permissions=permissions,
            )
            for (user, permissions) in get_users_with_perms(self, True).items()
        ]

    def resolve_assignable_permissions(self, info):
        if not info.context.user.has_perm("change_" + str(self._meta.model_name), self):
            return None

        if not isinstance(self, PermissionableModel):
            return None

        return self.available_permissions_for_user(info.context.user)


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


class ModelDeletionMutation(AuthRequiredMixin):
    """Generic model deletion mutation. Simply set the model in meta and you are away!"""

    class Meta:
        abstract = True

    class Arguments:
        id = IdInputField(required=True)

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
    # pylint: disable=W0212
    def authorize_request(cls, info, instance, *_, **__):
        """Authorize the request"""
        if cls._meta.ability:
            return cls._meta.ability.user_has(info.context.user, instance)

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

        # Authorize
        cls.authorize_request(info, model_instance)

        try:
            model_instance.delete()
        except RestrictedError as error:
            raise ReferencedException() from error

        return ModelDeletionMutation()


class AssignPermissionsMutation(AuthRequiredMixin):
    """Generic model deletion mutation. Simply set the model in meta and you are away!"""

    class Meta:
        abstract = True

    class Arguments:
        id = IdInputField(required=True)
        user_email = graphene.String(required=True)
        permissions = graphene.List(graphene.String)

    @classmethod
    def __init_subclass_with_meta__(
        cls, *args, model=None, ability=None, **options
    ):  # pragma: no cover
        """Inits the subclass with meta..."""
        if not model:
            raise Exception("model is required for AssignPermissionsMutation")

        if isinstance(model, PermissionableModel):
            raise Exception("model must be Permissionable")

        _meta = ModelDeletionMutationOptions(cls)
        _meta.model = model
        _meta.ability = ability

        super().__init_subclass_with_meta__(_meta=_meta, *args, **options)

    @classmethod
    # pylint: disable=W0212
    def authorize_request(
        cls, info, instance: PermissionableModel, permissions_delta, *_, **__
    ):
        """Authorize the request"""
        available_permissions = instance.available_permissions_for_user(
            info.context.user
        )

        if not info.context.user.has_perm(
            "change_" + cls._meta.model._meta.model_name, instance
        ):
            raise AuthorizationException()

        for permission in permissions_delta:
            # Try and get permission node for permission
            permission_node = next(
                (node for node in available_permissions if node.name == permission),
                None,
            )

            if not permission_node or not permission_node.user_can_assign:
                raise GQLException(
                    message="The permission '%s' does not exisit, or cannot be assigned"
                    % permission,
                    field="permissions",
                )

    @classmethod
    # pylint: disable=C0103,W0622
    def resolve_mutation(cls, _, info, id: int, user_email, permissions):
        model_instance = cls._meta.model.objects.get(id=id)

        # See if user exists

        if not (user := User.objects.filter(email=user_email).first()):
            raise GQLException(
                "A user with that email does not exist on our system",
                field="user_email",
            )

        available_permissions = [
            node.name
            for node in model_instance.available_permissions_for_user(info.context.user)
        ]

        current_user_permissions = set(
            get_user_perms(user, model_instance)
        ).intersection(available_permissions)

        permissions_to_remove = current_user_permissions - set(permissions)
        permissions_to_add = set(permissions).intersection(available_permissions) - set(
            current_user_permissions
        )

        permissions_delta = set(permissions_to_add) | set(permissions_to_remove)

        # Authorize
        cls.authorize_request(info, model_instance, permissions_delta)

        for permission in permissions_to_add:
            assign_perm(permission, user, model_instance)

        for permission in permissions_to_remove:
            remove_perm(permission, user, model_instance)

        return AssignPermissionsMutation()
