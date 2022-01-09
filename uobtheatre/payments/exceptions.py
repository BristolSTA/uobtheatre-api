from uobtheatre.utils.exceptions import GQLException


class CantBeRefundedException(GQLException):
    def __init__(self, message="This object cannot be refunded") -> None:
        super().__init__(message=message)
