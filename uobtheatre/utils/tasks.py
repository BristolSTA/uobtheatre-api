from celery import Task
from sentry_sdk import capture_exception


# Tasks
class BaseTask(Task):
    def on_failure(
        self, exc, task_id, args, kwargs, einfo
    ):  # pylint: disable=too-many-arguments
        capture_exception(exc)
        super().on_failure(exc, task_id, args, kwargs, einfo)
