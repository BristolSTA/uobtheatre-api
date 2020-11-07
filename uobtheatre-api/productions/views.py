from rest_framework import viewsets
from .models import Production 
from .serializers import ProductionSerializer


class ProductionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Production.objects.all()
    serializer_class = ProductionSerializer 
    fields = '__all__' 
