"""
Setups a few overrides for use throughout package
"""

from django.core.exceptions import EmptyResultSet
from django.db.models.sql import datastructures
from graphql_auth import bases

from uobtheatre.utils.exceptions import AuthOutput

from .celery import app as celery_app

# A disgusting but necessary hacky fix, once this issue is resolved we can
# remove, see: https://github.com/chibisov/drf-extensions/issues/294
datastructures.EmptyResultSet = EmptyResultSet  # type: ignore

# Override graphql_auth Output with our own custom output
bases.Output = AuthOutput

__all__ = ("celery_app",)
