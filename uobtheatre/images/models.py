from django.db import models
from graphql_relay.node.node import to_global_id


class Image(models.Model):
    """Model for images

    This model is a wrapper for ImageField, which adds some additional meta
    data.
    """

    file = models.ImageField()
    alt_text = models.CharField(max_length=50, null=True, blank=True)

    @property
    def global_id(self) -> str:
        return to_global_id("ImageNode", self.id)
