from django.apps import AppConfig


class ProductionsConfig(AppConfig):
    """Configuration for the productions app"""

    name = "uobtheatre.productions"
    verbose_name = "Productions"

    def ready(self):
        """Perform initialization tasks for this app (namely, register it's signals)"""
        import uobtheatre.productions.signals  # pylint: disable=unused-import
