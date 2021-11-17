"""
Defines the routes for the api
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView
from graphene_django.views import GraphQLView

from config.settings.common import SQUARE_SETTINGS
from uobtheatre.payments.square_webhooks import SquareWebhooks
from uobtheatre.images.views import ImageView

urlpatterns = [
    path(
        "graphql/",
        csrf_exempt(GraphQLView.as_view(graphiql=True)),
    ),
    path("reports/", include("uobtheatre.reports.urls")),
    path("admin/", admin.site.urls),
    path(SQUARE_SETTINGS["PATH"], SquareWebhooks.as_view()),
    # Redirect root to graphql
    re_path(r"^$", RedirectView.as_view(url="graphql/", permanent=False)),
    re_path(r"^upload/$", ImageView.as_view(), name="file-upload"),
] + static(settings.MEDIA_PATH, document_root=settings.MEDIA_ROOT)
