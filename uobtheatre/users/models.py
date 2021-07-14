import uuid
from typing import TYPE_CHECKING, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db import models

if TYPE_CHECKING:
    from uobtheatre.productions.models import Production


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

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def has_perm(self, model: str, query_object=None) -> bool:
        """
        Check if the user has access to a given model or object. If a user has
        acess to the model, they inherintly have access to all objects.

        Args:
            model (str): The model that the user may have access to.
            query_object (Model): The object that the user may have access to. It
                must have the same type as the model.

        Returns:
            bool: Whether the user has permission to access the object/model.
        """
        return super().has_perm(model) or (
            super().has_perm(model, query_object) if query_object else False
        )
