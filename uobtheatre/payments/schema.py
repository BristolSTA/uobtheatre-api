import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from uobtheatre.payments.models import Payment
from uobtheatre.utils.schema import FilterSet


class PaymentFilter(FilterSet):
    class Meta:
        model = Payment
        fields = "__all__"


class PaymentNode(DjangoObjectType):
    url = graphene.String(required=False)

    def resolve_url(self, info):
        return self.url()

    class Meta:
        model = Payment
        interfaces = (relay.Node,)
        filterset_class = PaymentFilter
