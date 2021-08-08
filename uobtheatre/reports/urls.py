from django.urls import path

from . import views

urlpatterns = [
    path("card_totals", views.card_totals, name="card_totals"),
    path(
        "outstanding_production_payments",
        views.outstanding_production_payments,
        name="outstanding_production_payments",
    ),
]
