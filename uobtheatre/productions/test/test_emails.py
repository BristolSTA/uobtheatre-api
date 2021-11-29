from unittest.mock import patch

import pytest

from uobtheatre.mail.composer import MailComposer
from uobtheatre.productions.emails import (
    send_production_approved_email,
    send_production_needs_changes_email,
    send_production_ready_for_review_email,
)
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_send_production_approved_email():
    user = UserFactory(email="myemail@example.org")
    production = ProductionFactory(name="My Production")

    with patch.object(MailComposer, "send") as send_mock:
        send_production_approved_email(user, production)
        send_mock.assert_called_once_with(
            "My Production has been approved", "myemail@example.org"
        )


@pytest.mark.django_db
def test_send_production_ready_for_review_email():
    user = UserFactory(email="myemail@example.org")
    production = ProductionFactory(name="My Production")

    with patch.object(MailComposer, "send") as send_mock:
        send_production_ready_for_review_email(user, production)
        send_mock.assert_called_once_with(
            "My Production is ready for approval", "myemail@example.org"
        )


@pytest.mark.django_db
def test_send_production_needs_changes_email():
    user = UserFactory(email="myemail@example.org")
    production = ProductionFactory(name="My Production")

    with patch.object(MailComposer, "send") as send_mock:
        send_production_needs_changes_email(user, production)
        send_mock.assert_called_once_with(
            "My Production needs changes", "myemail@example.org"
        )


@pytest.mark.django_db
def test_send_production_needs_changes_email_with_message():
    user = UserFactory(email="myemail@example.org")
    production = ProductionFactory(name="My Production")

    with patch.object(MailComposer, "send") as send_mock, patch.object(
        MailComposer, "line", wraps=MailComposer().line
    ) as line_mock:
        send_production_needs_changes_email(user, production, "You need to change!")
        line_mock.assert_any_call("Review Comment: 'You need to change!'")
        send_mock.assert_called_once_with(
            "My Production needs changes", "myemail@example.org"
        )
