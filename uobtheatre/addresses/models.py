from django.db import models


class Address(models.Model):
    """The model for an address"""

    building_name = models.CharField(max_length=255, null=True)
    building_number = models.CharField(max_length=10, null=True)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    postcode = models.CharField(max_length=9)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.building_name + ', ' if self.building_name else ''}{self.building_number + ', ' if self.building_number else ''}{self.street}, {self.city}, {self.postcode}"
