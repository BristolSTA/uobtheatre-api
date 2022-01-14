from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Configuration for the payments app"""

    name = "uobtheatre.payments"
    verbose_name = "Payments"

    def ready(self):
        """Perform initialization tasks for this app (namely, register it's signals)"""
        import uobtheatre.payments.signals  # pylint: disable=unused-import
