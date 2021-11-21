"""
Utils for uobtheatre modles
"""

import abc
from typing import Dict

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


class AbstractModelMeta(abc.ABCMeta, type(models.Model)):  # type: ignore
    pass


class TimeStampedMixin(models.Model):
    """Adds created_at and updated_at to a model

    Both created at and updated at are automatically set.
    """

    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PermissionableModel(models.Model):
    """A permissionable model allows for permissions to be assigned to the model at an object level via the API/Schema by authorised users"""

    class PermissionsMeta:
        """The format of schema_assignable_permissions should be a dict, with the permission as the key. Each entry should be a tuple of permission(s) that the user must have at least one of to assign/remove

        e.g. {
            "boxoffice": ("change_production","force_change_production")
        }
        """

        schema_assignable_permissions: Dict[str, tuple] = {}

    def available_permissions_for_user(self, user):
        """Returns a list of PermissionNodes, with details of name, description and whether the user provided is able to assign this permission"""
        from uobtheatre.utils.schema import PermissionNode

        assignable_permissions = self.PermissionsMeta.schema_assignable_permissions

        available_perms = Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(self),
        ).all()

        return [
            PermissionNode(
                name=permission.codename,
                description=permission.name,
                user_can_assign=any(
                    user.has_perm(permission, self)
                    for permission in assignable_permissions[permission.codename]
                )
                if permission.codename in assignable_permissions
                else False,
            )
            for permission in available_perms
        ]

    class Meta:
        abstract = True


def validate_percentage(percentage):
    """Validate a given percentage value

    A percentage value can only be between 0 and 1. If this is not the case a
    ValidationError is raised

    Args:
        (float): The percentage value to validate

    Raises:
        ValidationError: If the value is not valid
    """
    if not 0 <= percentage <= 1:
        raise ValidationError(
            f"The percentage {percentage} is not in the required range [0, 1]"
        )
