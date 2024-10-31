import django_filters
import graphene
from django.db.models.query_utils import Q
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.site_messages.models import Message
from uobtheatre.users.abilities import PermissionsMixin
from uobtheatre.utils.filters import FilterSet
from uobtheatre.utils.schema import UserPermissionFilterMixin, IdInputField


class SiteMessageByMethodOrderingFilter(django_filters.OrderingFilter):
    """Ordering filter for messages which adds display start, event start and event end.

    Extends the default implementation of OrderingFitler to include ordering
    (ascending and descending) of display start, event start and event end.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra["choices"] += [
            ("display_start", "Display Start"),
            ("-display_start", "Display Start (descending)"),
            ("start", "Start"),
            ("-start", "Start (descending)"),
            ("end", "End"),
            ("-end", "End (descending)"),
        ]

    def filter(self, query_set, value: str):
        """Fitler for display start, event start and event end of messages

        Adds following options:
         - 'display_start'
        - '-display_start' (Descending display start)
         - 'start'
         - '-start' (Descending start)
         - 'end'
         - '-end' (Descending end)

        Args:
            query_set (QuerySet): The Queryset which is being filtered.
            value (str): The choices s(eg 'start')

        Returns:
            Queryset: The filtered Queryset
        """
        if value and "display_start" in value:
            return query_set.annotate_start().order_by("display_start")
        if value and "-display_start" in value:
            return query_set.annotate_start().order_by("-display_start")
        
        if value and "start" in value:
            return query_set.annotate_start().order_by("start")
        if value and "-start" in value:
            return query_set.annotate_start().order_by("-start")

        if value and "end" in value:
            return query_set.annotate_end().order_by("end")
        if value and "-end" in value:
            return query_set.annotate_end().order_by("-end")

        return super().filter(query_set, value)


class SiteMessageFilterSet(FilterSet):
    """Filter for MessageNode

    Extends filterset to include display start, event start and event end.

    __gte is shorthand for greater than or equal to
    __lte is shorthand for less than or equal to
    """

    display_start = django_filters.DateTimeFilter(method="display_start_filter")
    display_start__gte = django_filters.DateTimeFilter(method="display_start_filter")
    display_start__lte = django_filters.DateTimeFilter(method="display_start_filter")

    start = django_filters.DateTimeFilter(method="start_filter")
    start__gte = django_filters.DateTimeFilter(method="start_filter")
    start__lte = django_filters.DateTimeFilter(method="start_filter")

    end = django_filters.DateTimeFilter(method="end_filter")
    end__gte = django_filters.DateTimeFilter(method="end_filter")
    end__lte = django_filters.DateTimeFilter(method="end_filter")

    to_display = django_filters.BooleanFilter(method = "to_display_filter")

    @classmethod
    def display_start_filter(cls, query_set, value, date=None):
        return query_set.annotate_display().filter(**{value: date})

    @classmethod
    def start_filter(cls, query_set, value, date=None):
        return query_set.annotate_start().filter(**{value: date})

    @classmethod
    def end_filter(cls, query_set, value, date=None):
        return query_set.annotate_end().filter(**{value: date})
    
    @classmethod
    def to_display_filter(cls, query_set, _, value):
        return query_set.to_display(value)

    class Meta:
        model = Message
        fields = '__all__'

    order_by = SiteMessageByMethodOrderingFilter()

class SiteMessageNode(DjangoObjectType):
    event_duration = graphene.Int()

    to_display = graphene.Boolean()

    def resolve_event_duration(self, info):
        return self.duration.total_seconds() // 60
    
    def resolve_to_display(self, info):
        return self.to_display

    class Meta:
        model = Message
        interfaces = (relay.Node,)
        filterset_class = SiteMessageFilterSet
        fields = (
            "id",
            "message",
            "active",
            "indefinite_override",
            "display_start",
            "event_start",
            "event_end",
            "type",
            "creator",
            "dismissal_policy",
            "event_duration",
            "to_display",
        )

class Query(graphene.ObjectType):
    site_messages = DjangoFilterConnectionField(SiteMessageNode)
    site_message = graphene.Field(SiteMessageNode, id=IdInputField(required=True))

    def resolve_site_message(self, _, id):
        try:
            return Message.objects.get(id=id)
        except Message.DoesNotExist:
            return None
