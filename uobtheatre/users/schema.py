from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.users.models import User


class UserNode(DjangoObjectType):
    class Meta:
        model = User
        interfaces = (relay.Node,)
        exclude = ("password",)
