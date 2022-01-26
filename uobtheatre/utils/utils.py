"""
Utils
"""

import itertools
from typing import List, Set, Tuple, TypeVar

import shortuuid


def create_short_uuid():
    return shortuuid.ShortUUID().random(length=12)


IterableType = TypeVar("IterableType")


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
