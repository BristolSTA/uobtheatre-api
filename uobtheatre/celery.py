import os

from celery import Celery, app

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
