from graphene_django import DjangoObjectType

from uobtheatre.finance.models import FinancialTransfer


class FinancialTransferNode(DjangoObjectType):
    class Meta:
        model = FinancialTransfer
