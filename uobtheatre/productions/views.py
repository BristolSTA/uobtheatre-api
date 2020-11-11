from rest_framework import viewsets
from .models import Production
from .serializers import ProductionSerializer
from rest_framework.decorators import action


class ProductionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows productions to be viewed or edited.
    """

    queryset = Production.objects.all()
    serializer_class = ProductionSerializer
    fields = "__all__"

    @action(detail=False)
    def upcoming_productions(self, request):
        """
        Action to return 6 upcoming productions. It will return the soonest
        next productions. The date of the production is based on the maximun
        (latest) end date of all the performaces.
        """
        future_productions = [
            production
            for production in Production.objects.all()
            if production.is_upcoming()
        ]
        future_productions.sort(key=lambda prod: prod.end_date(), reverse=False)
        page = self.paginate_queryset(future_productions[:6])

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(future_productions, many=True)
        return Response(serializer.data)
