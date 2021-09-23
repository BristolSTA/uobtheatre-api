import abc

import graphene
from guardian.shortcuts import get_perms


class AbilitiesMixin:
    """
    Mixin for model. Updates get_perms method to include abilites.
    """

    @property
    @abc.abstractmethod
    def abilities(self):
        raise NotImplementedError

    def get_perms(self, user, obj):
        django_perms = get_perms(user, self)
        computed_perms = [
            ability.name for ability in self.abilities if ability.user_has(user, obj)
        ]
        return django_perms + computed_perms


class Ability(abc.ABC):
    """
    Abilites are computed permission. This means the user is not explicitly
    assinged the permission but may or may not be allowed to do a thing based
    on other fields. For example if a user is a member of a society they may be
    able to access more information than a regular user.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def user_has(user, obj) -> bool:
        raise NotImplementedError


class OpenBoxoffice(Ability):
    """Whether the user has permission to open the boxoffice."""

    name = "boxoffice_open"

    @staticmethod
    def user_has(user, _) -> bool:
        from uobtheatre.productions.models import Performance  # type: ignore

        return Performance.objects.has_boxoffice_permission(user).exists()  # type: ignore


class OpenAdmin(Ability):
    """Whether the user has permission to open the admin pannel."""

    name = "admin_open"

    @staticmethod
    def user_has(user, _) -> bool:
        return user.is_superuser or user.has_any_objects_with_perms(
            [
                "productions.add_production",
                "productions.change_production",
                "productions.view_production",
            ]
        )


class PermissionsMixin:
    """
    Add permissions to schema. This is a list of string, if a string is
    included then the user has this permission.
    """

    permissions = graphene.List(graphene.String)

    def resolve_permissions(self, info):
        if hasattr(self, "get_perms"):
            return self.get_perms(info.context.user, self)
        return get_perms(info.context.user, self)
