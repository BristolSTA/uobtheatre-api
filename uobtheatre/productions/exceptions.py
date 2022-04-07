from uobtheatre.utils.exceptions import GQLException


class ClearanceAlreadyGivenException(GQLException):
    def __init__(self, clearance_type: str) -> None:
        super().__init__(message=f"{clearance_type.title()} clearance has already been given for this performance")
