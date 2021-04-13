import django_filters
from graphene_django.filter import GlobalIDFilter


class FilterSet(django_filters.FilterSet):
    id = GlobalIDFilter()
