import os

from .common import *

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DEBUG = True

# Testing
INSTALLED_APPS += ("django_nose",)
NOSE_ARGS = [
    BASE_DIR,
    "-s",
    "--nologcapture",
    "--with-coverage",
    "--with-progressive",
    "--cover-package=uobtheatre-api",
]

# Mail
EMAIL_HOST = "localhost"
EMAIL_PORT = 1025
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CORS_ORIGIN_ALLOW_ALL = True