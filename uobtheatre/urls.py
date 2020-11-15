from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path, reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework.authtoken import views
from rest_framework.routers import DefaultRouter

from uobtheatre.productions.views import ProductionViewSet
from uobtheatre.societies.views import SocietyViewSet
from uobtheatre.users.views import UserCreateViewSet, UserViewSet
from uobtheatre.venues.views import VenueViewSet
from uobtheatre.bookings.views import UserBookingViewSet

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

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"users", UserCreateViewSet)
router.register(r"productions", ProductionViewSet)
router.register(r"societies", SocietyViewSet)
router.register(r"venues", VenueViewSet)
router.register(r"bookings", UserBookingViewSet,basename='Booking')

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(router.urls)),
    path("api-token-auth/", views.obtain_auth_token),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    # the 'api-root' from django rest-frameworks default router
    # http://www.django-rest-framework.org/api-guide/routers/#defaultrouter
    re_path(r"^$", RedirectView.as_view(url=reverse_lazy("api-root"), permanent=False)),
    # Documentation
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
