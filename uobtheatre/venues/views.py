from rest_framework import viewsets

from uobtheatre.venues.models import Venue
from uobtheatre.venues.serializers import FullVenueSerializer


class VenueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Venues to be viewed or edited.
    """

    queryset = Venue.objects.all()
    serializer_class = FullVenueSerializer
    ordering = ["id"]
    lookup_field = "slug"