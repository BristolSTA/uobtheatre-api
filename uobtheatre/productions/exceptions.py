from uobtheatre.utils.exceptions import GQLException


class UnassignedSeatGroupException(GQLException):
    """Raised when an unassigned seat group is encountered"""


class UnassignedConcessionTypeException(GQLException):
    """Raised when an unassigned seat group is encountered"""


class CapacityException(GQLException):
    """Raised when a request would cause a performance/seat gorup to go over capacity"""
