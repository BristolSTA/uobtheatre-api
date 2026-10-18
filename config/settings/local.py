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

INTERNAL_IPS = [
    "127.0.0.1"
]

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": 'debug_toolbar.middleware.show_toolbar_with_docker'
}
