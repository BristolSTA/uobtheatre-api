import uuid
from typing import Union

from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from guardian.shortcuts import assign_perm, get_objects_for_user

from uobtheatre.users.abilities import AbilitiesMixin, OpenAdmin, OpenBoxoffice


class User(AbilitiesMixin, AbstractUser):
    """The model for users.

    A User is someone that uses the app (including admins). A user is
    identified by their email address (usernames are not used).
    """

    username = None  # type: ignore
    abilities = [OpenAdmin, OpenBoxoffice]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # type: ignore
    email = models.EmailField(
        max_length=254,
        verbose_name="email address",
        unique=True,
        null=False,
        blank=False,
    )
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = ["first_name", "last_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def has_perm(self, perm: str, obj=None) -> bool:
        """
        Check if the user has access to a given model or object. If a user has
        acess to the model, they inherintly have access to all objects.

        Args:
            perm (str): The permission that the user may or may not have, these
                are defined in the Meta class of the model.
            obj (Model): The object that the user may have access to. It
                must have the same type as the model.

        Returns:
            bool: Whether the user has permission to access the object/model.
        """
        return super().has_perm(perm) or (super().has_perm(perm, obj) if obj else False)

    def assign_perm(self, perm: str, obj=None):
        return assign_perm(perm, self, obj)

    def get_objects_with_perm(self, permissions: Union[str, list[str]]):
        """
        Returns all the objects which the user has the request permissions for.
        """
        return get_objects_for_user(self, permissions, any_perm=True)

    def has_any_objects_with_perms(self, permissions: Union[str, list[str]]) -> bool:
        """
        Given a list of permissions (or a single permission) returns if the
        user has this permission globally or for any objects.

        Args:
            permissions: (Union[str, list[str]]): The permissions being
                checked. If a list is provided only one of the permissions must
                be met to return True

        Returns:
            bool: Whether the user has any of the permissions
        """
        if isinstance(permissions, str):
            permissions = [permissions]

        return (
            # Here we check explicitly check global permissions as no objects
            # are returned if no objects exist for get_objects_with_perm.
            self.get_objects_with_perm(permissions).exists()
            or any(self.has_perm(perm) for perm in permissions)
        )

    @property
    def global_perms(self):
        if self.is_superuser:
            return Permission.objects.all()
        return self.user_permissions.all() | Permission.objects.filter(group__user=self)
