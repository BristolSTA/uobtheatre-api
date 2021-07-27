# pylint: disable=unused-wildcard-import,wildcard-import

import os

from .common import *

MEDIA_URL = f"{BASE_URL}{MEDIA_PATH}"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEBUG = True

# Mail
EMAIL_HOST = "localhost"
EMAIL_PORT = 1025
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_BACKEND = "anymail.backends.amazon_ses.EmailBackend"

# CORS
CORS_ORIGIN_ALLOW_ALL = True
