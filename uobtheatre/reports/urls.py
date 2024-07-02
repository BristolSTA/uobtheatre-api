from django.urls import path

from . import views

urlpatterns = [
    path(
        "period_totals/<str:start_time>/<str:end_time>",
        views.period_totals,  # type: ignore[arg-type]
        name="period_totals",
    ),
    path(
        "outstanding_society_payments",
        views.outstanding_society_payments,  # type: ignore[arg-type]
        name="outstanding_society_payments",
    ),
    path(
        "performance_bookings",
        views.performance_bookings,  # type: ignore[arg-type]
        name="performance_bookings",
    ),
]
