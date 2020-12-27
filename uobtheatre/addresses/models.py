from django.db import models


class Address(models.Model):
    """ An address """

    building_name = models.CharField(max_length=255)
    building_number = models.CharField(max_length=10)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    postcode = models.CharField(max_length=9)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.street}, {self.city}, {self.postcode}"
