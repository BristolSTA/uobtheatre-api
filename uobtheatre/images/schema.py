import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.images.models import Image


class ImageNode(DjangoObjectType):

    url = graphene.String()

    def resolve_url(self, info):
        return self.file.url

    class Meta:
        model = Image
        interfaces = (relay.Node,)
        fields = ("id", "url", "alt_text")
