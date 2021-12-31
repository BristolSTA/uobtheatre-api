from django.apps import AppConfig


class ProductionsConfig(AppConfig):
    name = "uobtheatre.productions"
    verbose_name = "Productions"

    def ready(self):
        import uobtheatre.productions.signals  # NOQA
