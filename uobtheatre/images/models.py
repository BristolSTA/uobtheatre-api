from django.db import models


class Image(models.Model):
    """ A seat which can be booked """

    file = models.ImageField()
    alt_text = models.CharField(max_length=50, null=True, blank=True)
