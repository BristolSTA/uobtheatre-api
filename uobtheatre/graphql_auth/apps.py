from django.apps import AppConfig


class GraphQLAuthConfig(AppConfig):
    name = "uobtheatre.graphql_auth"
    verbose_name = "GraphQL Auth"

    def ready(self):
        from . import signals
