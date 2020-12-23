from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin


from uobtheatre.productions.models import Production, Society, Performance
from uobtheatre.productions.serializers import (
    ProductionSerializer,
    SocietySerializer,
    PerformanceSerializer,
    PerformanceTicketTypesSerializer,
)


class ProductionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows productions to be viewed or edited.
    """

    queryset = Production.objects.all()
    serializer_class = ProductionSerializer
    ordering = ["id"]
    lookup_field = "slug"

    @action(detail=False)
    def upcoming_productions(self, request):
        """
        Action to return 6 upcoming productions. It will return the soonest
        next productions. The date of the production is based on the maximun
        (latest) end date of all the performaces. It returns in order of ending
        date st those which are ending soonest are returned first.
        """
        future_productions = [
            production
            for production in Production.objects.all()
            if production.is_upcoming()
        ]
        future_productions.sort(key=lambda prod: prod.end_date(), reverse=False)
        page = self.paginate_queryset(future_productions[:6])

        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class PerforamceViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    model = Performance
    queryset = Performance.objects.all()
    serializer_class = PerformanceSerializer
    ordering = ["id"]

    @action(detail=True)
    def ticket_types(self, request, parent_lookup_production__slug=None, pk=None):
        """
        Action to return all tickets types for the performance
        """
        serializer = PerformanceTicketTypesSerializer(self.get_object())
        return Response(serializer.data)
