from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.forms import SendEmailForm


@pytest.mark.django_db
@pytest.mark.parametrize("is_valid", [True, False])
def test_send_email_form_submit(is_valid):
    form = SendEmailForm(
        {
            "message": "My Message",
            "subject": "My Subject",
        },
        initial={
            "users": [UserFactory()],
            "user_reason": "My reason",
            "lgtm": True,
        },
    )
    form.is_valid()
    with patch.object(form, "is_valid", return_value=is_valid):
        if not is_valid:
            with pytest.raises(ValidationError):
                form.submit()
        else:
            with patch("uobtheatre.mail.composer.MassMailComposer.send") as send_mock:
                form.submit()
            send_mock.assert_called_once()
