from rest_framework import viewsets

from uobtheatre.societies.models import Society
from uobtheatre.societies.serializers import SocietySerializer


class SocietyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows societies to be viewed or edited.
    """

    queryset = Society.objects.all()
    serializer_class = SocietySerializer
