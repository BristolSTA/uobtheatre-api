from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = "uobtheatre.payments"
    verbose_name = "Payments"

    def ready(self):
        import uobtheatre.payments.signals  # NOQA
