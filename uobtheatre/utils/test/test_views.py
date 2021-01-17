import pytest
from rest_framework import viewsets

from uobtheatre.utils.views import ReadWriteSerializerMixin
from uobtheatre.venues.serializers import VenueSerializer


def test_read_write_serialzier_mixin_error():
    """
    When using the read write serializer mixin you must do one of the following:
     - Include a read_serializer_class
     - Overwrite get_read_serializer_class
     - Define read_serializer_class and detail_read_serializer_class
    If not an error should be thrown
    """

    class TestViewSet(ReadWriteSerializerMixin, viewsets.GenericViewSet):
        pass

    test_view = TestViewSet()
    test_view.action = ""

    with pytest.raises(AssertionError):
        test_view.get_read_serializer_class()


def test_read_write_serialzier_mixin_uses_read_serializer_class():
    """
    If list_read_serializer_class and detail_read_serializer_class are not used
    the view should default the read_serializer_class
    """

    class TestViewSet(ReadWriteSerializerMixin, viewsets.GenericViewSet):
        read_serializer_class = VenueSerializer

    test_view = TestViewSet()
    test_view.action = ""

    test_view.get_read_serializer_class() == VenueSerializer
