from django.db import models


class Image(models.Model):
    """Model for the images

    This model is a wrapper for ImageField, which adds some additional meta
    data.
    """

    file = models.ImageField()
    alt_text = models.CharField(max_length=50, null=True, blank=True)
