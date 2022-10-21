from uobtheatre.utils.exceptions import GQLException


class NotBookableException(GQLException):
    """NotEnoughCapacityExceptionoking for a performance that is not bookable is requested"""

    def __init__(self, message="Performance not bookable") -> None:
        super().__init__(message)


class InvalidSeatGroupException(GQLException):
    """Raised when a seat group is supplied that is invalid for a given performance"""

    def __init__(
        self,
        message="The supplied seat group is not valid for the given performance",
        **kwargs
    ) -> None:
        super().__init__(message=message, **kwargs)


class InvalidConcessionTypeException(GQLException):
    """Raised when a concession type is supplied that is invalid for a given performance"""

    def __init__(
        self,
        message="The supplied concession type is not valid for the given performance",
        **kwargs
    ) -> None:
        super().__init__(message=message, **kwargs)


class NotEnoughCapacityException(GQLException):
    """Raised when there is not enough capacity in a given object (performance, seat group, etc.)"""

    def __init__(
        self, message="There is not enough capacity available", **kwargs
    ) -> None:
        super().__init__(message=message, **kwargs)
