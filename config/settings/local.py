# pylint: disable=unused-wildcard-import,wildcard-import

import os

from .common import *

MEDIA_URL = f"{BASE_URL}{MEDIA_PATH}"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEBUG = True

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

# CORS
CORS_ORIGIN_ALLOW_ALL = True
