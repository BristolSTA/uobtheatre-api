import os

from .common import *  # noqa: F403,F401

BASE_URL = "http://localhost:8000"
MEDIA_URL = f"{BASE_URL}{MEDIA_PATH}"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DEBUG = True

# Mail
EMAIL_HOST = "localhost"
EMAIL_PORT = 1025
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CORS
CORS_ORIGIN_ALLOW_ALL = True
