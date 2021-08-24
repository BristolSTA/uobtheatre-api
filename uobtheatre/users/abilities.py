import abc

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
    def user_has(user, item) -> bool:
        raise NotImplementedError


class OpenBoxoffice(Ability):
    """Whether the user has permission to open the boxoffice."""

    name = "boxoffice_open"

    @staticmethod
    def user_has(user, _) -> bool:
        from uobtheatre.productions.models import Performance

        return (
            Performance.objects.has_boxoffice_permission(user).count()  #  type: ignore
            > 0
        )


class OpenAdmin(Ability):
    """Whether the user has permission to open the admin pannel."""

    name = "admin_open"

    @staticmethod
    def user_has(user, _) -> bool:
        # TODO check if the user can edit or create productions
        return user.is_superuser
