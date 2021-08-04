import uuid
from typing import TYPE_CHECKING, List

from django.contrib.auth.models import AbstractUser
from django.db import models

from uobtheatre.productions.models import Performance

if TYPE_CHECKING:
    pass


class User(AbstractUser):
    """The model for users.

    A User is someone that uses the app (including admins). A user is
    identified by their email address (usernames are not used).
    """

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
    REQUIRED_FIELDS: List[str] = ["first_name", "last_name"]

    @property
    def can_boxoffice(self):
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
