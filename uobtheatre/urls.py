from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path, reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from graphene_django.views import GraphQLView
from rest_framework import permissions
from rest_framework.documentation import include_docs_urls
from rest_framework_extensions.routers import ExtendedDefaultRouter

from uobtheatre.bookings.views import BookingViewSet
from uobtheatre.productions.views import PerforamceViewSet, ProductionViewSet
from uobtheatre.societies.views import SocietyViewSet
from uobtheatre.users.views import UserCreateViewSet, UserViewSet
from uobtheatre.venues.views import VenueViewSet

# GraphQLView.graphiql_template = "graphene_graphiql_explorer/graphiql.html"

# Documentation setup
schema_view = get_schema_view(
    openapi.Info(
        title="UOB Theatre API",
        default_version="v1",
        description="The api for uob theatre",
        # terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="webmaster@bristolsta.com"),
        # license=openapi.License(name="None"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

router = ExtendedDefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"users", UserCreateViewSet)
router.register(r"productions", ProductionViewSet).register(
    r"performances",
    PerforamceViewSet,
    basename="production-performances",
    parents_query_lookups=["production__slug"],
)
router.register(r"societies", SocietyViewSet)
router.register(r"venues", VenueViewSet)
router.register(r"bookings", BookingViewSet, basename="Booking")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("docs/", include_docs_urls(title="UOB Theatre")),
    path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True))),
    path("api/v1/", include(router.urls)),
    # Authentication
    path("api/v1/auth/", include("rest_auth.urls")),
    path("api/v1/auth/registration/", include("rest_auth.registration.urls")),
    # the 'api-root' from django rest-frameworks default router
    # http://www.django-rest-framework.org/api-guide/routers/#defaultrouter
    re_path(r"^$", RedirectView.as_view(url=reverse_lazy("api-root"), permanent=False)),
    # Documentation
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
