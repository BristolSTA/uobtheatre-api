from rest_framework import viewsets

from uobtheatre.venues.models import Venue
from uobtheatre.venues.serializers import VenueSerializer


class VenueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows societies to be viewed or edited.
    """

    queryset = Venue.objects.all()
    serializer_class = VenueSerializer
