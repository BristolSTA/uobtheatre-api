from typing import TYPE_CHECKING

from celery import Task
from django.core.mail import mail_admins
from sentry_sdk import capture_exception

if TYPE_CHECKING:
    pass

# Tasks
class BaseTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        capture_exception(exc)
        super().on_failure(exec, task_id, args, kwargs, einfo)


