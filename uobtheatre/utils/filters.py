from typing import Callable, Union

import django_filters
from django.db import models
from django.db.models.base import Model
from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet
from graphene_django.filter import GlobalIDFilter


class FilterSet(django_filters.FilterSet):
    id = GlobalIDFilter()


class Instance(models.Model):
    objects = models.Manager()


def filter_passes_on_model(
    instance: Instance,
    filter_function: Callable[[Union[QuerySet, BaseManager]], QuerySet],
):
    """Run a filter on an individual model instance to see if it passes"""
    return filter_function(instance.__class__.objects).filter(pk=instance.pk).exists()
