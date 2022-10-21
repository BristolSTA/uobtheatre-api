import abc
from typing import TYPE_CHECKING, Any

import graphene
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import get_perms

if TYPE_CHECKING:
    from uobtheatre.users.models import User


class AbilitiesMixin:
    """
    Mixin for model. Updates get_perms method to include abilites.
    """

    @property
    @abc.abstractmethod
    def abilities(self):
        raise NotImplementedError

    def get_perms(self, user, obj):
        """Override get_perms method to return perms as well as abilities"""
        django_perms = get_perms(user, self)
        computed_perms = [
            ability.name
            for ability in self.abilities
            if ability.user_has_for(user, obj)
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

    @classmethod
    def user_has(cls, user: "User") -> bool:  # pylint: disable=unused-argument
        """Returns whether the user has the ability for any / at all

        Args:
            user (User): The user being queried

        Returns:
            bool: Whether the user has the abiltiy
        """
        return False

    @classmethod
    # pylint: disable=unused-argument
    def user_has_for(cls, user: "User", obj: Any) -> bool:
        """Returns whether the user has the ability for a specific object

        Args:
            user (User): The user being queried
            obj (Model): The object to query the user on

        Returns:
            bool: Whether the user has the ability for the object
        """
        return cls.user_has(user)


class AllwaysPasses(Ability):
    @classmethod
    def user_has(cls, user) -> bool:
        return True


class OpenBoxoffice(Ability):
    """Whether the user has permission to open the boxoffice."""

    name = "boxoffice_open"

    @staticmethod
    def user_has(user) -> bool:
        from uobtheatre.productions.models import Performance  # type: ignore

        return Performance.objects.has_boxoffice_permission(user).exists()  # type: ignore


class OpenAdmin(Ability):
    """Whether the user has permission to open the admin panel."""

    name = "admin_open"

    @staticmethod
    def user_has(user) -> bool:
        from uobtheatre.productions.abilities import AddProduction

        return (
            user.has_any_objects_with_perms(
                [
                    "productions.add_production",
                    "productions.change_production",
                    "productions.view_production",
                ]
            )
            or user.has_any_objects_with_perms(["societies.add_production"])
            or user.has_perm("reports.finance_reports")
            or AddProduction.user_has(user)
        )


class PermissionsMixin:
    """
    Add permissions to schema. This is a list of string, if a string is
    included then the user has this permission.
    """

    permissions = graphene.List(graphene.String)

    def resolve_permissions(self, info):
        global_perms = [
            perm.codename
            for perm in list(
                info.context.user.user_permissions.filter(
                    content_type=ContentType.objects.get_for_model(self)
                ).all()
            )
            + list(
                Permission.objects.filter(
                    group__id__in=info.context.user.groups.values_list("id", flat=True),
                    content_type=ContentType.objects.get_for_model(self),
                ).all()
            )
        ]
        if hasattr(self, "get_perms"):
            return self.get_perms(info.context.user, self) + global_perms
        return get_perms(info.context.user, self) + global_perms
