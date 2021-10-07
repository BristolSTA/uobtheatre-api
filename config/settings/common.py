import os
from datetime import timedelta
from distutils.util import strtobool
from os.path import join
from typing import List

import environ

env = environ.Env()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = os.getenv(
    "BASE_URL",
    default="http://localhost:8000",
)

INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third party apps
    # Authentiaction
    "graphql_auth",  # Graphql authentication (user setup)
    "graphql_jwt.refresh_token.apps.RefreshTokenConfig",
    ##
    "django_filters",  # for filtering rest endpoints
    "corsheaders",  # CORS
    "autoslug",  # Auto slug
    "graphene_django",  # Graphql
    "guardian",
    "django_tiptap",
    "rest_framework",
    "django_inlinecss",
    # Your apps
    "uobtheatre.users",
    "uobtheatre.productions",
    "uobtheatre.utils",
    "uobtheatre.venues",
    "uobtheatre.bookings",
    "uobtheatre.discounts",
    "uobtheatre.societies",
    "uobtheatre.addresses",
    "uobtheatre.payments",
    "uobtheatre.images",
    "uobtheatre.reports",
    "uobtheatre.mail",
    "uobtheatre",
)

# https://docs.djangoproject.com/en/2.0/topics/http/middleware/
MIDDLEWARE = (
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
)

ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "uobtheatre.urls"
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    default="Ha57AUXmBdFS48TKYPMhauspK7BhwpveyvM9PGsCwwcT7RfwUN2rVkYnbuXkWhcU",
)
WSGI_APPLICATION = "config.wsgi.application"

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = os.getenv("EMAIL_PORT") or 1025
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = "UOB Theatre <no-reply@uobtheatre.com>"

ADMINS = (("Author", "webmaster@bristolsta.com"),)


# Postgres
if os.getenv("DATABASE_URL"):  # ignore:
    DATABASES = {"default": env.db("DATABASE_URL", "")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql_psycopg2",
            "NAME": os.getenv("POSTGRES_DB", default="postgres"),
            "USER": os.getenv("POSTGRES_USER", default="postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", default="postgres"),
            "HOST": os.getenv("POSTGRES_HOST", default="postgres"),
            "PORT": os.getenv("POSTGRES_PORT", default="5432"),
        }
    }
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# General
APPEND_SLASH = False
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False
USE_L10N = True
USE_TZ = True
LOGIN_REDIRECT_URL = "/"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/
STATIC_ROOT = os.path.normpath(join(BASE_DIR, "staticfiles"))
STATICFILES_DIRS: List[str] = [
    os.path.normpath(join(BASE_DIR, "static"))
]
STATIC_URL = "/static/"
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

# Media files
MEDIA_ROOT = join(BASE_DIR, "media")
MEDIA_PATH = "/media/"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": STATICFILES_DIRS,
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Set DEBUG to False as a default for safety
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = strtobool(os.getenv("DJANGO_DEBUG", "no"))

# Password Validation
# https://docs.djangoproject.com/en/2.0/topics/auth/passwords/#module-django.contrib.auth.password_validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "graphql_auth.backends.GraphQLAuthBackend",
    "guardian.backends.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[%(server_time)s] %(message)s",
        },
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["require_debug_true"],
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "debug.log",
        },
        "allfile": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "debugall.log",
        },
    },
    "loggers": {
        "": {"handlers": ["allfile"], "level": "DEBUG", "propagate": True},
        "django": {
            "handlers": ["console", "file"],
            "propagate": True,
        },
        "django.server": {
            "handlers": ["django.server", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["mail_admins", "console", "file"],
            "level": "ERROR",
            "propagate": True,
        },
        "django.db.backends": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "uobtheatre": {"handlers": ["file"], "level": "INFO", "propagate": True},
        "psycopg2": {"handlers": ["file"], "level": "INFO", "propagate": True},
    },
}

# Custom user app
AUTH_USER_MODEL = "users.User"
GRAPHQL_AUTH = {
    "LOGIN_ALLOWED_FIELDS": ["email"],
    "USER_NODE_EXCLUDE_FIELDS": ["password"],
    "USER_NODE_FILTER_FIELDS": {
        "email": ["exact", "icontains", "istartswith"],
        "is_active": ["exact"],
        "status__archived": ["exact"],
        "status__verified": ["exact"],
        "status__secondary_email": ["exact"],
    },
    "REGISTER_MUTATION_FIELDS": ["email", "first_name", "last_name"],
    "REGISTER_MUTATION_FIELDS_OPTIONAL": [],
    "ALLOW_LOGIN_NOT_VERIFIED": False,
    "ACTIVATION_PATH_ON_EMAIL": "login/activate",
    "ACTIVATION_SECONDARY_EMAIL_PATH_ON_EMAIL": "user/email-verify",
    "PASSWORD_RESET_PATH_ON_EMAIL": "login/forgot",
    "EMAIL_TEMPLATE_ACTIVATION": "emails/activation_email.html",
    "EMAIL_TEMPLATE_SECONDARY_EMAIL_ACTIVATION": "emails/activation_email.html",
    "EMAIL_TEMPLATE_PASSWORD_RESET": "emails/password_reset_email.html",
}


GRAPHQL_JWT = {
    "JWT_ALLOW_ANY_CLASSES": [
        "graphql_auth.mutations.Register",
        "graphql_auth.mutations.VerifyAccount",
        "graphql_auth.mutations.ResendActivationEmail",
        "graphql_auth.mutations.SendPasswordResetEmail",
        "graphql_auth.mutations.PasswordReset",
        "graphql_auth.mutations.ObtainJSONWebToken",
        "graphql_auth.mutations.VerifyToken",
        "graphql_auth.mutations.RefreshToken",
        "graphql_auth.mutations.RevokeToken",
        "graphql_auth.mutations.VerifySecondaryEmail",
    ],
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_LONG_RUNNING_REFRESH_TOKEN": True,
    "JWT_EXPIRATION_DELTA": timedelta(minutes=5),
    "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=365),
}

GRAPHENE = {
    "SCHEMA": "uobtheatre.schema.schema",
    "MIDDLEWARE": [
        "graphql_jwt.middleware.JSONWebTokenMiddleware",
        "uobtheatre.utils.exceptions.ExceptionMiddleware",
    ],
}

# Square payments
SQUARE_SETTINGS = {
    "SQUARE_ACCESS_TOKEN": os.getenv(
        "SQUARE_ACCESS_TOKEN",
        default="",
    ),
    "SQUARE_ENVIRONMENT": os.getenv(
        "SQUARE_ENVIRONMENT",
        default="sandbox",
    ),
    "SQUARE_LOCATION": os.getenv(
        "SQUARE_LOCATION",
        default="",
    ),
    "SQUARE_WEBHOOK_SIGNATURE_KEY": os.getenv(
        "SQUARE_WEBHOOK_SIGNATURE_KEY",
        default="",
    ),
    "PATH": "square",
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
