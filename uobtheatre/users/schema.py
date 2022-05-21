import graphene
from graphql_auth import mutations, schema
from graphql_relay.node.node import to_global_id

from uobtheatre.users.models import User


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


class AuthMutation(graphene.ObjectType):
    """User mutations

    Adds mutations to schema from graphql_auth package.
    """

    register = mutations.Register.Field()
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
