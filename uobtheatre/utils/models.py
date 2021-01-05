from django.db import models


class TimeStampedMixin:
    """Adds created_at and updated_at to a model"""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReadWriteSerializerMixin(object):
    """
    Overrides get_serializer_class to choose the read serializer
    for GET requests and the write serializer for POST requests.

    Set read_serializer_class and write_serializer_class attributes on a
    viewset.
    """

    # Serializer used for reading (overriden by below)
    read_serializer_class = None
    # Serializer used for reading list
    list_read_serializer_class = None
    # Serializer used for reading detailed
    detail_read_serializer_class = None

    write_serializer_class = None

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return self.get_write_serializer_class()
        return self.get_read_serializer_class()

    def get_read_serializer_class(self):
        print(f"The action is: {self.action}")
        if self.action == "list" and self.list_read_serializer_class:
            return self.list_read_serializer_class
        if self.action == "retrieve" and self.detail_read_serializer_class:
            return self.detail_read_serializer_class
        assert self.read_serializer_class is not None, (
            "'%s' should either include a `read_serializer_class` attribute,"
            "or override the `get_read_serializer_class()` method or include"
            "both list_read_serializer_class and detail_read_serializer_class."
            % self.__class__.__name__
        )
        return self.read_serializer_class

    def get_write_serializer_class(self):
        assert self.write_serializer_class is not None, (
            "'%s' should either include a `write_serializer_class` attribute,"
            "or override the `get_write_serializer_class()` method."
            % self.__class__.__name__
        )
        return self.write_serializer_class
