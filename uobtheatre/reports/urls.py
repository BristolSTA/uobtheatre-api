from django.urls import path

from . import views

urlpatterns = [
    path("period_totals", views.period_totals, name="period_totals"),
    path(
        "outstanding_society_payments",
        views.outstanding_society_payments,
        name="outstanding_society_payments",
    ),
]
