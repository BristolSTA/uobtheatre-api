from unittest.mock import patch

from uobtheatre.utils.tasks import BaseTask


def test_base_task_on_failure():
    task = BaseTask()
    exception = Exception("test")

    with patch(
        "uobtheatre.utils.tasks.capture_exception"
    ) as mock_capture_exception, patch("celery.Task.on_failure") as super_on_failure:
        task.on_failure(exception, "abc", tuple(), {}, None)

    mock_capture_exception.assert_called_once_with(exception)
    super_on_failure.assert_called_once_with(exception, "abc", tuple(), {}, None)
