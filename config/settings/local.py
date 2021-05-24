# pylint: disable=unused-wildcard-import,wildcard-import

import os

from .common import *

MEDIA_URL = f"{BASE_URL}{MEDIA_PATH}"
print(f"BASE_URL is {BASE_URL}")
print(f"MEDIA_URL is {MEDIA_URL}")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEBUG = True

# Mail
EMAIL_HOST = "localhost"
EMAIL_PORT = 1025
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CORS
CORS_ORIGIN_ALLOW_ALL = True
