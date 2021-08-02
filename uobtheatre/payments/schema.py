import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.bookings.schema import BookingNode
from uobtheatre.payments.models import Payment
from uobtheatre.payments.square import PaymentProvider
from uobtheatre.utils.enums import GrapheneEnumMixin
from uobtheatre.utils.filters import FilterSet
from uobtheatre.utils.schema import SafeMutation


class PaymentFilter(FilterSet):
    class Meta:
        model = Payment
        fields = ("type", "provider", "created_at")


class PayObjectUnion(graphene.Union):
    class Meta:
        types = (BookingNode,)


class SquarePaymentDevice(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    code = graphene.String()
    device_id = graphene.String()


class PaymentNode(GrapheneEnumMixin, DjangoObjectType):
    url = graphene.String(required=False)
    pay_object = PayObjectUnion()

    def resolve_url(self, info):
        return self.url()

    class Meta:
        model = Payment
        interfaces = (relay.Node,)
        filterset_class = PaymentFilter
        exclude = ("pay_object_id", "pay_object_type")


class CreateDeviceCode(SafeMutation):
    """Mutation to generate device code using name.

    Args:
        name (str): The name of the device

    Returns:
        code (str): Returns the code of the device

    Raises:
    """

    code = graphene.String()

    class Arguments:
        name = graphene.String(required=True)

    @classmethod
    def resolve_mutation(cls, _, __, name):
        payment_provider = PaymentProvider()
        code = payment_provider.create_device_code(name)
        return CreateDeviceCode(code=code)


class Query(graphene.ObjectType):
    square_devices = graphene.List(SquarePaymentDevice)

    def resolve_square_devices(self, _):
        payment_provider = PaymentProvider()
        return [
            SquarePaymentDevice(
                id=device["id"],
                name=device["name"],
                code=device["code"],
                device_id=device["device_id"],
            )
            for device in payment_provider.list_pos_devices()
        ]


class Mutation(graphene.ObjectType):
    create_device_code = CreateDeviceCode.Field()
