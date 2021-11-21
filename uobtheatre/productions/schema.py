from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
import django_filters
import graphene
from django.db.models.query_utils import Q
from graphene import relay
from graphene.types.field import Field
from graphene_django import DjangoListField
from graphene_django.filter import DjangoFilterConnectionField

from uobtheatre.discounts.schema import ConcessionTypeNode, DiscountNode
from uobtheatre.productions.abilities import AddProduction, EditProductionObjects
from uobtheatre.productions.forms import (
    PerformanceForm,
    PerformanceSeatGroupForm,
    ProductionForm,
)
from uobtheatre.productions.models import (
    AudienceWarning,
    CastMember,
    CrewMember,
    CrewRole,
    Performance,
    PerformanceSeatGroup,
    Production,
    ProductionTeamMember,
)
from uobtheatre.users.abilities import PermissionsMixin
from uobtheatre.users.schema import AuthMutation
from uobtheatre.utils.filters import FilterSet
from uobtheatre.utils.schema import (
    AssignedUsersMixin,
    AuthRequiredMixin,
    DjangoObjectType,
    GrapheneEnumMixin,
    ModelDeletionMutation,
    SafeFormMutation,
)

ProductionStatusSchema = graphene.Enum.from_enum(Production.Status)


class CrewRoleNode(GrapheneEnumMixin, DjangoObjectType):
    class Meta:
        model = CrewRole
        interfaces = (relay.Node,)


class CastMemberNode(DjangoObjectType):
    class Meta:
        model = CastMember
        interfaces = (relay.Node,)


class ProductionTeamMemberNode(DjangoObjectType):
    class Meta:
        model = ProductionTeamMember
        interfaces = (relay.Node,)


class CrewMemberNode(DjangoObjectType):
    class Meta:
        model = CrewMember
        interfaces = (relay.Node,)


class WarningNode(DjangoObjectType):
    class Meta:
        model = AudienceWarning
        interfaces = (relay.Node,)


class ProductionByMethodOrderingFilter(django_filters.OrderingFilter):
    """Ordering filter for productions which adds start and end.

    Extends the default implementation of OrderingFitler to include ordering
    (ascending and descending) of production start and end time.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra["choices"] += [
            ("start", "Start"),
            ("-start", "Start (descending)"),
            ("end", "End"),
            ("-end", "End (descending)"),
        ]

    def filter(self, query_set, value: str):
        """Fitler for start and end of production

        Adds following options:
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
        if value and "start" in value:
            return query_set.annotate_start().order_by("start")
        if value and "-start" in value:
            return query_set.annotate_start().order_by("-start")

        if value and "end" in value:
            return query_set.annotate_end().order_by("end")
        if value and "-end" in value:
            return query_set.annotate_end().order_by("-end")

        return super().filter(query_set, value)


class ProductionFilter(FilterSet):
    """Filter for ProductionNode

    Extends filterset to include start and end filters.
    """

    start = django_filters.DateTimeFilter(method="start_filter")
    start__gte = django_filters.DateTimeFilter(method="start_filter")
    start__lte = django_filters.DateTimeFilter(method="start_filter")

    end = django_filters.DateTimeFilter(method="end_filter")
    end__gte = django_filters.DateTimeFilter(method="end_filter")
    end__lte = django_filters.DateTimeFilter(method="end_filter")

    search = django_filters.CharFilter(method="search_productions", label="Search")

    def start_filter(self, query_set, value, date=None):
        return query_set.annotate_start().filter(**{value: date})

    def end_filter(self, query_set, value, date=None):
        return query_set.annotate_end().filter(**{value: date})

    def search_productions(self, queryset, _, value):
        """
        Given a query string, searches through the productions using the name of the production

        Args:
            queryset (Queryset): The productions queryset.
            value (str): The search query.

        Returns:
            Queryset: Filtered booking queryset.
        """
        query = Q()
        for word in value.split():
            query = query | Q(name__icontains=word)
        return queryset.filter(query)

    class Meta:
        model = Production
        exclude = ("poster_image", "featured_image", "cover_image")

    order_by = ProductionByMethodOrderingFilter()


class SalesBreakdownNode(graphene.ObjectType):
    total_sales = graphene.Int(required=True)
    total_card_sales = graphene.Int(required=True)
    provider_payment_value = graphene.Int(required=True)
    app_payment_value = graphene.Int(required=True)
    society_transfer_value = graphene.Int(required=True)
    society_revenue = graphene.Int(required=True)


class ProductionNode(
    PermissionsMixin, GrapheneEnumMixin, DjangoObjectType, AssignedUsersMixin
):
    warnings = DjangoListField(WarningNode)
    crew = DjangoListField(CrewMemberNode)
    cast = DjangoListField(CastMemberNode)
    production_team = DjangoListField(ProductionTeamMemberNode)

    start = graphene.DateTime()
    end = graphene.DateTime()

    is_bookable = graphene.Boolean(required=True)
    min_seat_price = graphene.Int()

    sales_breakdown = graphene.Field(SalesBreakdownNode)
    total_capacity = graphene.Int(required=True)
    total_tickets_sold = graphene.Int(required=True)

    def resolve_start(self, info):
        return self.start_date()

    def resolve_end(self, info):
        return self.end_date()

    def resolve_is_bookable(self, info):
        return self.is_bookable()

    def resolve_min_seat_price(self, info):
        return self.min_seat_price()

    def resolve_sales_breakdown(self, info):
        if not info.context.user.has_perm("productions.sales", self):
            return None

        return SalesBreakdownNode(**self.sales_breakdown())

    def resolve_total_capacity(self, info):
        return self.total_capacity

    def resolve_total_tickets_sold(self, info):
        return self.total_tickets_sold

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.user_can_see(info.context.user)

    class Meta:
        model = Production
        filterset_class = ProductionFilter
        interfaces = (relay.Node,)


class ProductionMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a production"""

    production = Field(ProductionNode)

    @classmethod
    def authorize_request(cls, root, info, **mInput):
        return super().authorize_request(
            root, info, **mInput
        ) and cls.authorize_society_part(root, info, **mInput)

    @classmethod
    def authorize_society_part(cls, root, info, **mInput):
        """Authorise the society parameter if passed"""
        new_society = cls.get_python_value(root, info, "society", **mInput)
        has_perm_new_society = (
            info.context.user.has_perm("add_production", new_society)
            if new_society
            else True
        )
        return has_perm_new_society

    @classmethod
    def on_creation(cls, info, response):
        info.context.user.assign_perm("view_production", response.production)
        info.context.user.assign_perm("change_production", response.production)
        info.context.user.assign_perm("sales", response.production)
        info.context.user.assign_perm("boxoffice", response.production)

    class Meta:
        form_class = ProductionForm
        create_ability = AddProduction
        update_ability = EditProductionObjects


class ConcessionTypeBookingType(graphene.ObjectType):
    """Node for ConcessionType which can be Booked.

    This object gives the information about a ConcessionType for a given
    production. It includes the concession type and its pricing.
    """

    concession_type = graphene.Field(ConcessionTypeNode)
    price = graphene.Int()
    price_pounds = graphene.String()

    def resolve_price_pounds(self, info):
        return "%.2f" % (self.price / 100)


class PerformanceSeatGroupNode(DjangoObjectType):
    capacity_remaining = graphene.Int()
    concession_types = graphene.List(ConcessionTypeBookingType)

    def resolve_concession_types(self, info):
        return [
            ConcessionTypeBookingType(
                concession_type=concession,
                price=self.performance.price_with_concession(concession, self),
            )
            for concession in self.performance.concessions()
        ]

    def resolve_capacity_remaining(self, info):
        return self.performance.capacity_remaining(self.seat_group)

    class Meta:
        model = PerformanceSeatGroup
        fields = (
            "capacity",
            "capacity_remaining",
            "concession_types",
            "seat_group",
            "performance",
            "price",
        )
        filter_fields = {}  # type: ignore
        interfaces = (relay.Node,)


class PerformanceFilter(FilterSet):
    """Filter for PerformanceNode.

    Extends filterset to include orderby start.
    """

    has_boxoffice_permissions = django_filters.BooleanFilter(
        method="has_boxoffice_perm_filter"
    )
    run_on = django_filters.DateFilter(method="run_on_filter")

    class Meta:
        model = Performance
        exclude = ("performance_seat_groups", "bookings")

    order_by = django_filters.OrderingFilter(fields=(("start"),))

    def has_boxoffice_perm_filter(self, query_set, _, has_permission=None):
        return query_set.has_boxoffice_permission(
            self.request.user, has_permission=has_permission
        )

    def run_on_filter(self, query_set, _, date=None):
        return query_set.running_on(date)


class PerformanceTicketsBreakdown(graphene.ObjectType):
    total_capacity = graphene.Int(required=True)
    total_tickets_sold = graphene.Int(required=True)
    total_tickets_checked_in = graphene.Int(required=True)
    total_tickets_to_check_in = graphene.Int(required=True)
    total_tickets_available = graphene.Int(required=True)


class PerformanceNode(DjangoObjectType):
    capacity_remaining = graphene.Int()
    ticket_options = graphene.List(PerformanceSeatGroupNode)
    min_seat_price = graphene.Int()
    duration_mins = graphene.Int()
    is_inperson = graphene.Boolean(required=True)
    is_online = graphene.Boolean(required=True)
    sold_out = graphene.Boolean(required=True)
    is_bookable = graphene.Boolean(required=True)
    discounts = DjangoListField(DiscountNode)
    tickets_breakdown = graphene.Field(PerformanceTicketsBreakdown, required=True)
    sales_breakdown = graphene.Field(SalesBreakdownNode)

    def resolve_ticket_options(self, info):
        return self.performance_seat_groups.all()

    def resolve_capacity_remaining(self, info):
        return self.capacity_remaining()

    def resolve_min_seat_price(self, info):
        return self.min_seat_price()

    def resolve_is_inperson(self, info):
        return True

    def resolve_is_online(self, info):
        return False

    def resolve_duration_mins(self, info):
        return self.duration().seconds // 60

    def resolve_sold_out(self, info):
        return self.is_sold_out

    def resolve_tickets_breakdown(self, info):
        return PerformanceTicketsBreakdown(
            self.total_capacity,
            self.total_tickets_sold(),
            self.total_tickets_checked_in,
            self.total_tickets_unchecked_in,
            self.capacity_remaining(),
        )

    def resolve_sales_breakdown(self, info):
        if not info.context.user.has_perm(
            "productions.sales",
            self.production,
        ):
            return None

        return SalesBreakdownNode(**self.sales_breakdown())

    def resolve_is_bookable(self, info):
        return self.is_bookable

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.user_can_see(info.context.user)

    class Meta:
        model = Performance
        filterset_class = PerformanceFilter
        interfaces = (relay.Node,)
        exclude = ("performance_seat_groups",)


class PerformanceMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a performance"""

    performance = Field(PerformanceNode)

    @classmethod
    def authorize_request(cls, root, info, **mInput):
        return cls.authorize_production_part(root, info, **mInput)

    @classmethod
    def authorize_production_part(cls, root, info, **mInput):
        """Authorised the production part (exisiting and prodivded input)"""
        new_production = cls.get_python_value(root, info, "production", **mInput)
        has_perm_new_production = (
            EditProductionObjects.user_has(info.context.user, new_production)
            if new_production
            else True
        )

        if cls.is_creation:
            # If this is a creation operation, we care that there is a new production specified via args, and that the user has edit ability on this production
            return has_perm_new_production and new_production

        # For update operations, we care that the user has permissions on both the currently assigned production, and the new production (if provided)
        current_production = cls.get_object_instance(root, info, **mInput).production
        has_perm_current_production = EditProductionObjects.user_has(
            info.context.user, current_production
        )
        return has_perm_new_production and has_perm_current_production

    class Meta:
        form_class = PerformanceForm


class DeletePerformanceMutation(ModelDeletionMutation):
    """Mutation to delete a performance"""

    class Meta:
        model = Performance


class PerformanceSeatGroupMutation(SafeFormMutation, AuthRequiredMixin):
    """Mutation to create or update a performance seat group"""

    performanceSeatGroup = Field(PerformanceSeatGroupNode)

    @classmethod
    def authorize_request(cls, root, info, **mInput):
        new_performance = cls.get_python_value(root, info, "performance", **mInput)
        has_perm_new_performance = (
            EditProductionObjects.user_has(info.context.user, new_performance)
            if new_performance
            else True
        )

        if cls.is_creation:
            # If this is a creation operation, we care that there is a new performance specified via args, and that the user has edit ability on this production
            return has_perm_new_performance and new_performance

        # For update operations, we care that the user has permissions on both the currently assigned performance, and the new performance (if provided)
        current_performance = cls.get_object_instance(
            root, info, **mInput
        ).performance.production
        has_perm_current_performance = EditProductionObjects.user_has(
            info.context.user, current_performance
        )
        return has_perm_new_performance and has_perm_current_performance

    class Meta:
        form_class = PerformanceSeatGroupForm


class DeletePerformanceSeatGroupMutation(ModelDeletionMutation):
    """Mutation to delete a performance seat group"""

    @classmethod
    def authorize_request(cls, _, info, id):
        instance = cls.get_instance(id)
        return EditProductionObjects.user_has(
            info.context.user,
            instance.performance.production,
        )

    class Meta:
        model = PerformanceSeatGroup


class Query(graphene.ObjectType):
    """Query for production module.

    These queries are appended to the main schema Query.
    """

    productions = DjangoFilterConnectionField(ProductionNode)
    performances = DjangoFilterConnectionField(PerformanceNode)

    production = graphene.Field(ProductionNode, slug=graphene.String(required=True))
    performance = relay.Node.Field(PerformanceNode)

    def resolve_production(self, info, slug):
        try:
            return Production.objects.user_can_see(info.context.user).get(slug=slug)
        except Production.DoesNotExist:
            return None


class Mutation(AuthMutation, graphene.ObjectType):
    """Mutations for the productions module"""

    production = ProductionMutation.Field()

    performance = PerformanceMutation.Field()
    delete_performance = DeletePerformanceMutation.Field()

    performance_seat_group = PerformanceSeatGroupMutation.Field()
    delete_performance_seat_group = DeletePerformanceSeatGroupMutation.Field()
