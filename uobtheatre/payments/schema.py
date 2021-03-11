import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.bookings.schema import BookingNode
from uobtheatre.payments.models import Payment
from uobtheatre.utils.schema import FilterSet


class PaymentFilter(FilterSet):
    class Meta:
        model = Payment
        fields = ("type", "provider", "created_at")


class PayObjectUnion(graphene.Union):
    class Meta:
        types = (BookingNode,)


class PaymentNode(DjangoObjectType):
    url = graphene.String(required=False)
    pay_object = PayObjectUnion()

    def resolve_url(self, info):
        return self.url()

    class Meta:
        model = Payment
        interfaces = (relay.Node,)
        filterset_class = PaymentFilter
        exclude = ("pay_object_id", "pay_object_type")
