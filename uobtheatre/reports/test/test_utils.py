import time
from datetime import timedelta
from unittest.mock import patch

import pytest

from uobtheatre.reports.exceptions import InvalidReportSignature
from uobtheatre.reports.utils import (
    generate_report_download_signature,
    validate_report_download_signature,
)
from uobtheatre.users.test.factories import UserFactory


def test_validate_report_signature_with_none():
    with pytest.raises(InvalidReportSignature):
        validate_report_download_signature(None)


@pytest.mark.django_db
def test_validate_report_signature_with_valid():
    user = UserFactory()
    valid_signature = generate_report_download_signature(user, "MyReport", [])
    assert validate_report_download_signature(valid_signature) == {
        "user_id": str(user.id),
        "report": "MyReport",
        "options": [],
    }


def test_validate_report_signature_with_invalid():
    with pytest.raises(InvalidReportSignature):
        validate_report_download_signature("notAValidSignature")


@pytest.mark.django_db
def test_validate_expired_report_signature():
    with patch.object(
        time,
        "time",
        return_value=time.time() - timedelta(minutes=12).seconds,
    ):
        signature = generate_report_download_signature(UserFactory(), "MyReport", [])

    with pytest.raises(InvalidReportSignature):
        validate_report_download_signature(signature)
