from functools import cached_property

import pytz
from django.db import models
from timezonefinder import TimezoneFinder

from uobtheatre.utils.validators import ValidationError


class Address(models.Model):
    """The model for an address"""

    building_name = models.CharField(max_length=255, blank=True, null=True)
    building_number = models.CharField(max_length=10, blank=True, null=True)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    postcode = models.CharField(max_length=9)
    what3words = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="A what3words address, taking the form '///word.word.word'",
    )
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    @cached_property
    def timezone(self):
        """Returns the timezone at the address"""
        if not self.latitude or not self.longitude:
            return pytz.UTC

        finder = TimezoneFinder()
        timezone = finder.timezone_at(lat=self.latitude, lng=self.longitude)
        return pytz.timezone(timezone) if timezone else pytz.UTC

    def clean(self):
        """Validate the model data on save"""
        super().clean()

        # Check that the what3words address is valid (starts with /// and has 3 words separated by dots)
        if self.what3words:
            if not self.what3words.startswith("///"):
                raise ValidationError("The what3words address must start with '///'.")
            if len(self.what3words.split(".")) != 3:
                raise ValidationError(
                    "The what3words address must contain 3 words separated by dots."
                )

    def save(self, *args, **kwargs):
        """Override save to ensure model is cleaned before saving"""
        # In the future, when adding functionality to change addresses by mutation,
        # this and clean() will need to be called in the mutation resolver via a form

        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.building_name + ', ' if self.building_name else ''}{self.building_number + ', ' if self.building_number else ''}{self.street}, {self.city}, {self.postcode}"
