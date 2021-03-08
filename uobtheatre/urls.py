from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView
from graphene_django.views import GraphQLView

# GraphQLView.graphiql_template = "graphene_graphiql_explorer/graphiql.html"

urlpatterns = [
    path(
        "graphql/",
        csrf_exempt(GraphQLView.as_view(graphiql=True)),
    ),
    path("admin/", admin.site.urls),
    # path("docs/", include_docs_urls(title="UOB Theatre")),
    # Authentication
    # path("api/v1/auth/", include("rest_auth.urls")),
    # path("api/v1/auth/registration/", include("rest_auth.registration.urls")),
    # the 'api-root' from django rest-frameworks default router
    # http://www.django-rest-framework.org/api-guide/routers/#defaultrouter
    re_path(r"^$", RedirectView.as_view(url="graphql/", permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
