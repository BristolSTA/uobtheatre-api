import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.schema import BookingNode
from uobtheatre.payments.models import Payment
from uobtheatre.utils.schema import FilterSet


class PaymentFilter(FilterSet):
    class Meta:
        model = Payment
        fields = "__all__"


class PayObjectUnion(graphene.Union):
    class Meta:
        types = (BookingNode,)


class PaymentNode(DjangoObjectType):
    url = graphene.String(required=False)
    pay_object = PayObjectUnion()

    def resolve_url(self, info):
        return self.url()

    def resolve_pay_object(self, info):
        if isinstance(self.pay_object, Booking):
            return self.pay_object

    class Meta:
        model = Payment
        interfaces = (relay.Node,)
        filterset_class = PaymentFilter
        exclude = ("pay_object_id", "pay_object_type")
