# pylint: disable=unused-wildcard-import,wildcard-import

import os

from .common import *

MEDIA_URL = f"{BASE_URL}{MEDIA_PATH}"

DEBUG = True

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

# CORS
CORS_ALLOW_ALL_ORIGINS = True

CELERY_WORKER_REDIRECT_STDOUTS_LEVEL = "INFO"

MIDDLEWARE = ("debug_toolbar.middleware.DebugToolbarMiddleware",) + MIDDLEWARE  # type: ignore

INSTALLED_APPS += ("debug_toolbar",)  # type: ignore

INTERNAL_IPS = [
    "127.0.0.1"
]

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": 'debug_toolbar.middleware.show_toolbar_with_docker'
}

DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.history.HistoryPanel',
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.alerts.AlertsPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.community.CommunityPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    'debug_toolbar.panels.profiling.ProfilingPanel',
    'cachalot.panels.CachalotPanel'
]