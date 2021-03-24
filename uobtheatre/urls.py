"""
Defines the routes for the api
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView
from graphene_django.views import GraphQLView

urlpatterns = [
    path(
        "graphql/",
        csrf_exempt(GraphQLView.as_view(graphiql=True)),
    ),
    path("admin/", admin.site.urls),
    # Redirect root to graphql
    re_path(r"^$", RedirectView.as_view(url="graphql/", permanent=False)),
] + static(settings.MEDIA_PATH, document_root=settings.MEDIA_ROOT)
