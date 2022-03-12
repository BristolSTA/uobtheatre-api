# pylint: skip-file

import os

from boto3.session import Session

from .common import *

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")  # type: ignore
CORS_ALLOWED_ORIGINS = [
    "https://uobtheatre.com",
    "https://staging.uobtheatre.com",
]

# Site
# https://docs.djangoproject.com/en/2.0/ref/settings/#allowed-hosts
INSTALLED_APPS += ("gunicorn",)  # type: ignore

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/
# http://django-storages.readthedocs.org/en/latest/index.html
INSTALLED_APPS += ("storages",)  # type: ignore
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_DEFAULT_ACL = "public-read"
AWS_AUTO_CREATE_BUCKET = True
AWS_QUERYSTRING_AUTH = False
MEDIA_URL = f"https://s3.amazonaws.com/{AWS_STORAGE_BUCKET_NAME}/"

STATICFILES_LOCATION = "static"
STATICFILES_STORAGE = "uobtheatre.storages.StaticStorage"

MEDIAFILES_LOCATION = "media"
DEFAULT_FILE_STORAGE = "uobtheatre.storages.MediaStorage"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if sentry_dns := os.getenv("SENTRY_DNS"):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=sentry_dns,
        integrations=[DjangoIntegration()],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=0.01,
        # If you wish to associate users to errors (assuming you are using
        # django.contrib.auth) you may enable sending PII data.
        send_default_pii=True,
    )

# https://developers.google.com/web/fundamentals/performance/optimizing-content-efficiency/http-caching#cache-control
# Response can be cached by browser and any intermediary caches (i.e. it is "public") for up to 1 day
# 86400 = (60 seconds x 60 minutes x 24 hours)
AWS_HEADERS = {
    "Cache-Control": "max-age=86400, s-maxage=86400, must-revalidate",
}

# Cloudwath logging
logger_boto3_session = Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)
LOGGING["formatters"]["aws"] = {  # type: ignore
    "aws": {
        "format": "%(asctime)s [%(levelname)-8s] %(message)s [%(pathname)s:%(lineno)d]",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    },
}
LOGGING["handlers"]["cloudwatch"] = {  # type: ignore
    "level": "INFO",
    "class": "watchtower.CloudWatchLogHandler",
    # From step 2
    "boto3_session": logger_boto3_session,
    "log_group": "DemoLogs",
    # Different stream for each environment
    "stream_name": f"logs",
    "formatter": "aws",
}
LOGGING["handlers"]["loggers"] = {  # type: ignore
    # Use this logger to send data just to Cloudwatch
    "cloudwatch": {
        "level": "INFO",
        "handlers": ["cloudwatch"],
        "propogate": False,
    }
}

EMAIL_BACKEND = (
    "anymail.backends.amazon_ses.EmailBackend"
    if strtobool(env("EMAIL_ENABLED", default="yes"))
    else "django.core.mail.backends.console.EmailBackend"
)


SQS_BROKER_URL = f"sqs://{AWS_ACCESS_KEY_ID}:{AWS_SECRET_ACCESS_KEY}@"
CELERY_BROKER_URL = SQS_BROKER_URL
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "queue_name_prefix": env("CELERY_QUEUE_PREFIX"),
    "region": env("AWS_DEFAULT_REGION", default="eu-west-2"),
}
