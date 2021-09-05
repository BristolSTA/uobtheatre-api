import uuid
from typing import Union

from django.contrib.auth.models import AbstractUser
from django.db import models
from guardian.shortcuts import get_objects_for_user

from uobtheatre.productions.models import Performance
from uobtheatre.users.abilities import AbilitiesMixin, OpenAdmin, OpenBoxoffice


class User(AbilitiesMixin, AbstractUser):
    """The model for users.

    A User is someone that uses the app (including admins). A user is
    identified by their email address (usernames are not used).
    """

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

    @property
    def can_boxoffice(self):
        """
        Returns whether the user can access the boxoffice region of the
        website.
        """
        return Performance.objects.has_boxoffice_permission(self).count() > 0

    def __str__(self):
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

    def get_objects_with_perm(self, permissions: Union[str, list[str]]):
        """
        Returns all the objects which the user has the request permissions for.
        """
        return get_objects_for_user(self, permissions)

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
        return (
            # Here we check explicitly check global permissions as no objects
            # are returned if no objects exist for get_objects_with_perm.
            any(self.has_perm(perm) for perm in permissions)
            or self.get_objects_with_perm(permissions).exists()
        )
