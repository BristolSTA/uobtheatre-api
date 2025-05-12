from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.addresses.models import Address


class AddressNode(DjangoObjectType):
    class Meta:
        model = Address
        interfaces = (relay.Node,)
        fields = (
            "building_name",
            "building_number",
            "street",
            "city",
            "postcode",
            "what3words",
            "latitude",
            "longitude",
        )
