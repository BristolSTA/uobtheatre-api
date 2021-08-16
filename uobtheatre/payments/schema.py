import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.bookings.schema import BookingNode
from uobtheatre.payments.models import Payment
from uobtheatre.payments.payment_methods import PaymentMethod, SquarePOS
from uobtheatre.utils.enums import GrapheneEnumMixin
from uobtheatre.utils.filters import FilterSet

PaymentMethodsEnum = graphene.Enum("PaymentMethod", PaymentMethod.choices)


class PaymentFilter(FilterSet):
    class Meta:
        model = Payment
        fields = ("type", "provider", "created_at")


class PayObjectUnion(graphene.Union):
    class Meta:
        types = (BookingNode,)


class SquarePaymentDevice(graphene.ObjectType):
    """
    Graphql object for square device
    """

    id = graphene.String()
    name = graphene.String()
    code = graphene.String()
    device_id = graphene.String()
    location_id = graphene.String()
    product_type = graphene.String()
    status = graphene.String()


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


class Query(graphene.ObjectType):
    """
    Base query for payments
    """

    payment_devices = graphene.List(
        SquarePaymentDevice,
        payment_provider=graphene.Argument(PaymentMethodsEnum),
        paired=graphene.Boolean(),
    )

    def resolve_payment_devices(
        self, _, payment_provider: str = None, paired: bool = None
    ):
        """
        Returns square payment devices.

        Args:
            payment_provider (str): Filter to only show devices related to
                this payment provider.
            paired (bool): Filter to only show devices that have been paired.

        Returns:
            list of SquarePaymentDevice: The square devices
        """

        devices = []
        include_all = not payment_provider

        if include_all or payment_provider == SquarePOS.name:
            status = None if paired is None else "PAIRED" if paired else "UNPAIRED"

            devices.extend(
                [
                    SquarePaymentDevice(
                        id=device["id"],
                        name=device["name"],
                        code=device["code"],
                        status=device["status"],
                        product_type=device["product_type"],
                        location_id=device["location_id"],
                        device_id=device.get("device_id"),
                    )
                    for device in SquarePOS.list_devices(
                        product_type="TERMINAL_API", status=status
                    )
                ]
            )

        return devices
