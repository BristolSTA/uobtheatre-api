import uuid
import factory
from datetime import datetime
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models.query import QuerySet
from rest_framework.authtoken.models import Token


class TimeStampedMixin:
    """Adds created_at and updated_at to a model"""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SoftDeletionQuerySet(QuerySet):
    def delete(self):
        return super(SoftDeletionQuerySet, self).update(deleted_at=timezone.now())

    def hard_delete(self):
        return super(SoftDeletionQuerySet, self).delete()

    def alive(self):
        return self.filter(deleted_at=None)

    def dead(self):
        return self.exclude(deleted_at=None)


class SoftDeletionManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.alive_only = kwargs.pop("alive_only", True)
        super(SoftDeletionManager, self).__init__(*args, **kwargs)

    def get_queryset(self):
        if self.alive_only:
            return SoftDeletionQuerySet(self.model).filter(deleted_at=None)
        return SoftDeletionQuerySet(self.model)

    def hard_delete(self):
        return self.get_queryset().hard_delete()


class SoftDeletionMixin:
    """Model that allows soft delte. This set the model to deleted (disabled)
    but does remove it from the db. A hard delete will remove it completely.
    """

    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = SoftDeletionManager()
    all_objects = SoftDeletionManager(alive_only=False)

    def delete(self):
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        self.deleted_at = None
        self.save()

    def hard_delete(self):
        super(SoftDeletionModel, self).delete()


class Society(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A society is a society"""

    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Venue(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A venue is a space often where shows take place"""

    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Production(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A production is a show (like the 2 weeks things) and can have many
    performaces (these are like the nights).
    """

    name = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, null=True)
    description = models.TextField(null=True)
    society = models.ForeignKey(Society, on_delete=models.SET_NULL, null=True)
    poster_image = models.ImageField(null=True)
    featured_image = models.ImageField(null=True)

    def __str__(self):
        return self.name


class Performance(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A performance is a discrete event when the show takes place eg 7pm on
    Tuesday.
    """

    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="performances"
    )
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)

    def __str__(self):
        if self.start is None:
            return f"Perforamce of {self.production.name}"
        return f"Perforamce of {self.production.name} at {self.start.strftime('%H:%M')} on {self.start.strftime('%m/%d/%Y')}"
