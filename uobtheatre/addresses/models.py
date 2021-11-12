from functools import cached_property

import pytz
from django.db import models
from timezonefinder import TimezoneFinder


class Address(models.Model):
    """The model for an address"""

    building_name = models.CharField(max_length=255, blank=True, null=True)
    building_number = models.CharField(max_length=10, blank=True, null=True)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    postcode = models.CharField(max_length=9)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    @cached_property
    def timezone(self):
        """Returns the timezone at the address"""
        if not self.latitude or not self.longitude:
            return pytz.UTC

        finder = TimezoneFinder()
        return pytz.timezone(finder.timezone_at(lat=self.latitude, lng=self.longitude))

    def __str__(self):
        return f"{self.building_name + ', ' if self.building_name else ''}{self.building_number + ', ' if self.building_number else ''}{self.street}, {self.city}, {self.postcode}"
