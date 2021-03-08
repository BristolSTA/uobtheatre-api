from django.core.exceptions import EmptyResultSet
from django.db.models.sql import datastructures
from graphql_auth import bases

from uobtheatre.utils.exceptions import AuthOutput

"""
A disgusting but necissary hacky fix
Once this issue is resolved we can remove
https://github.com/chibisov/drf-extensions/issues/294
"""
datastructures.EmptyResultSet = EmptyResultSet  # type: ignore

bases.Output = AuthOutput
