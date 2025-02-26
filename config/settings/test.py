# pylint: disable=unused-wildcard-import,wildcard-import

import logging
import tempfile

from .local import *  # noqa: F403,F401

logging.getLogger("faker").setLevel(logging.INFO)
logging.getLogger("factory").setLevel(logging.INFO)

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
DEBUG = True
TEST_RUNNER = "django.test.runner.DiscoverRunner"
BASE_URL = "https://api.example.com"

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    }
}

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES[-1]["APP_DIRS"] = False  # type: ignore[index] # noqa F405
TEMPLATES[-1]["OPTIONS"]["loaders"] = [  # type: ignore[index] # noqa F405
    (
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    )
]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# MEDIA
# ------------------------------------------------------------------------------
MEDIA_ROOT = tempfile.mkdtemp()

# OTHER
# ------------------------------------------------------------------------------
SQUARE_SETTINGS["SQUARE_LOCATION"] = "LMHPTEST"
