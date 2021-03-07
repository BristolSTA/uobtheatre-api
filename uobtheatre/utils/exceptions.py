import graphene

# https://gist.github.com/smmoosavi/033deffe834e6417ed6bb55188a05c88
# TODO We should probably raise these error instead and then format for you in
# the mutation, ie in mutation mixin wrap the mutation funciton in a try and
# handle errors there
# class GQLFieldError(Exception):
#     """
#     A single GQL Field error
#     """
#
#     def __init__(self, message, field=None, code=None, params=None):
#         super().__init__()
#         self.message = str(message)
#         self.code = code
#         self.params = params
#         self.field = field
# class GQLNonFieldError(Exception):
#     """
#     A single GQL Field error
#     """
#
#     def __init__(self, message, code=None):
#         super().__init__()
#         self.message = str(message)
#         self.code = code


class NonFieldError(graphene.ObjectType):
    message = graphene.String()
    code = graphene.String()


class FieldError(graphene.ObjectType):
    message = graphene.String()
    field = graphene.String()
    code = graphene.String()


class GQLErrorUnion(graphene.Union):
    class Meta:
        types = (FieldError, NonFieldError)


class MutationResult:
    success = graphene.Boolean(default_value=True)
    errors = graphene.List(GQLErrorUnion)


# TODO add errors to sentry
class ErrorMiddleware(object):
    def on_error(self, error):
        raise error

    def resolve(self, next, root, info, **args):
        return next(root, info, **args).catch(self.on_error)


class AuthOutput(MutationResult):
    """
    Overwrites the output class used in graphql_auth. This allows for custom
    error handling.
    """

    def resolve_errors(self, info):
        if self.errors is None:
            return

        if isinstance(self.errors, list):
            non_field_errors = [
                NonFieldError(error["message"], code=error["code"])
                for error in self.errors
            ]
            return non_field_errors
        if isinstance(self.errors, dict):
            non_field_errors = [
                NonFieldError(error.message, code=error.code)
                for error in self.errors.pop("field_errors", [])
            ]
            field_errors = [
                FieldError(error["message"], field=field, code=error["code"])
                for field, errors in self.errors.items()
                for error in errors
            ]
            return non_field_errors + field_errors

        raise Exception("Internal error")
