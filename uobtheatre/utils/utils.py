"""
Utils
"""

import itertools
from functools import reduce
from typing import List, Optional, Sequence, Set, Tuple, TypeVar

import shortuuid
from django.db.models import Model, Q, QuerySet


def create_short_uuid():
    return shortuuid.ShortUUID().random(length=12)


IterableType = TypeVar("IterableType")  # pylint: disable=invalid-name
ModelType = TypeVar("ModelType", bound=Model)  # pylint: disable=invalid-name


def normalise_email(email: str) -> str:
    """Return an email address in the form it is stored in.

    Email addresses are treated as case-insensitive, so they are stored in
    lower case. This stops one address from making two accounts.

    Args:
        email (str): The email address as it was entered.

    Returns:
        str: The email address in lower case.
    """
    return email.lower()


def get_by_email(
    queryset: QuerySet[ModelType],
    email: str,
    fields: Sequence[str] = ("email",),
) -> Optional[ModelType]:
    """Return the first object whose email matches, ignoring case.

    An exact match is tried first. Some older accounts only differ by the case
    of their email, and this keeps each of them reachable by its own address.

    Args:
        queryset (QuerySet): The objects to search.
        email (str): The email address to look for.
        fields (Sequence[str]): The email fields to check. A match on any one
            of them counts.

    Returns:
        Optional[Model]: The first matching object, or None if none match.
    """
    for lookup in ("exact", "iexact"):
        query = Q()
        for field in fields:
            query |= Q(**{f"{field}__{lookup}": email})
        if match := queryset.filter(query).first():
            return match
    return None


def combinations(
    iterable: List[IterableType], max_length: int
) -> Set[Tuple[IterableType, ...]]:
    """Return all subsets of input list upto a max length.

    Args:
        iterable (list of Any): The list which is used to find all the subsets.
        max_length (int): The maximum length of the sub sets to return, this
            must be smaller than or equal to the size of the provided iterable.

    Returns:
        (list of tuples of Any): Returns a list containing all the subsets of
            the input list.
    """
    return set(
        combination
        for i in range(1, max_length + 1)
        for combination in itertools.combinations(iterable * i, i)
    )


def deep_get(dictionary, keys, default=None):
    return reduce(
        lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
        keys.split("."),
        dictionary,
    )
