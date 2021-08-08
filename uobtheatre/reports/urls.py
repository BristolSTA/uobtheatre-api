from django.urls import path

from . import views

urlpatterns = [path("card_totals", views.card_totals, name="card_totals")]
