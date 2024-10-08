"""
Utils for uobtheatre modles
"""

import abc
from typing import Dict

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from graphql_relay.node.node import to_global_id


class classproperty:  # pylint: disable=invalid-name
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, obj, owner):
        return self.fget(owner)


class BaseModel(models.Model):
    """
    Base model for all UOB models. TODO actually use this
    """

    @property
    def qs(self):
        return self.__class__.objects.filter(pk=self.pk)  # type: ignore

    def clone(self):
        model = self.qs.get()
        model.pk = None
        return model

    @property
    def content_type(self):
        return ContentType.objects.get_for_model(self)

    @classmethod
    @classproperty
    def _node_name(cls):
        return f"{cls.__name__}Node"

    @property
    def global_id(self):
        return to_global_id(self._node_name, self.pk)

    class Meta:
        abstract = True


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
                user_can_assign=(
                    any(
                        user.has_perm(permission, self)
                        for permission in assignable_permissions[permission.codename]
                    )
                    if permission.codename in assignable_permissions
                    else False
                ),
            )
            for permission in available_perms
        ]

    class Meta:
        abstract = True
