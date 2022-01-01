from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.base import Model
from django.db.models.query_utils import Q
from guardian.shortcuts import get_users_with_perms

from uobtheatre.users.models import User


def get_users_with_perm(permission: str, obj: Model):
    """Get users with a specific global or object-level permission"""
    # First, get users with that permission out right
    split_perm = permission.split(".")
    codename = split_perm[1] if len(split_perm) > 1 else split_perm[0]
    content_type = ContentType.objects.get_for_model(obj)

    perm = Permission.objects.filter(
        content_type=content_type,
    ).get(codename=codename)

    global_users_with_permission = User.objects.filter(
        Q(groups__permissions__in=[perm]) | Q(user_permissions__in=[perm])
    )

    return get_users_with_perms(
        obj,
        with_superusers=True,
        only_with_perms_in=[codename],
    ).union(global_users_with_permission)
