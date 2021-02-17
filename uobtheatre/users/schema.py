import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.users.models import User


class UserNode(DjangoObjectType):
    class Meta:
        model = User
        interfaces = (relay.Node,)
        exclude = ("password",)


class Query(graphene.ObjectType):
    auth_user = graphene.Field(UserNode)

    def resolve_auth_user(self, info):
        if info.context.user.is_authenticated:
            return info.context.user
