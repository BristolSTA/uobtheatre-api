import graphene
from graphql_auth import mutations, schema
from graphql_relay.node.node import to_global_id

from uobtheatre.users.models import User
from uobtheatre.users.turnstile import validate


class ExtendedUserNode(schema.UserNode):
    """
    Extends user node to add additional properties.
    """

    id = graphene.String()
    permissions = graphene.List(graphene.String)

    def resolve_id(self, info):
        return to_global_id("UserNode", self.id)

    def resolve_permissions(self, info):
        global_perms = [perm.codename for perm in self.global_perms.all()]
        computed_perms = [
            ability.name
            for ability in self.abilities
            if ability.user_has(info.context.user)
        ]
        return global_perms + computed_perms

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "date_joined",
            "bookings",
            "created_bookings",
            "permissions",
        )


class TurnstileMixin(graphene.Mutation):
    """
    Verifies a recaptcha with turnstile
    """

    @classmethod
    def Field(cls, *args, **kwargs):
        cls._meta.arguments.update({"turnstile_token": graphene.String(required=True)})
        return super().Field(*args, **kwargs)

    @classmethod
    def mutate(cls, root, info, **inputs):
        """
        Intercepts the mutation to validate the turnstile token before proceeding.
        """
        # Validate Turnstile
        turnstile_response = validate(inputs.get("turnstile_token", ""))
        if not turnstile_response.success:
            return cls(
                success=False,
                errors={
                    "FieldErrors": [
                        {
                            "message": "".join(turnstile_response.error_codes),
                            "field": "turnstileToken",
                            "code": "turnstileTokenReject",
                        }
                    ]
                },
            )
        # Remove Turnstile from input
        inputs.pop("turnstile_token")
        return super().mutate(root, info, **inputs)


class RegisterTurnstile(TurnstileMixin, mutations.Register):
    """
    Registers a new user with Turnstile verification.
    """


class AuthMutation(graphene.ObjectType):
    """User mutations

    Adds mutations to schema from graphql_auth package.
    """

    register = RegisterTurnstile.Field()
    verify_account = mutations.VerifyAccount.Field()
    resend_activation_email = mutations.ResendActivationEmail.Field()
    send_password_reset_email = mutations.SendPasswordResetEmail.Field()
    password_reset = mutations.PasswordReset.Field()
    password_set = mutations.PasswordSet.Field()  # For passwordless registration
    password_change = mutations.PasswordChange.Field()
    update_account = mutations.UpdateAccount.Field()
    archive_account = mutations.ArchiveAccount.Field()
    delete_account = mutations.DeleteAccount.Field()
    send_secondary_email_activation = mutations.SendSecondaryEmailActivation.Field()
    verify_secondary_email = mutations.VerifySecondaryEmail.Field()
    swap_emails = mutations.SwapEmails.Field()
    remove_secondary_email = mutations.RemoveSecondaryEmail.Field()

    # django-graphql-jwt inheritances
    login = mutations.ObtainJSONWebToken.Field()
    verify_token = mutations.VerifyToken.Field()
    refresh_token = mutations.RefreshToken.Field()
    revoke_token = mutations.RevokeToken.Field()


class ExtendedMeQuery(graphene.ObjectType):
    """
    Extends user node to add additional properties.
    """

    me = graphene.Field(ExtendedUserNode)

    def resolve_me(self, info):
        user = info.context.user
        if user.is_authenticated:
            return user
        return None


class Query(ExtendedMeQuery, graphene.ObjectType):
    pass


class Mutation(AuthMutation, graphene.ObjectType):
    pass
