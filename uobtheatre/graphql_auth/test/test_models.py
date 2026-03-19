import pytest
from types import SimpleNamespace
from unittest import mock

from uobtheatre.graphql_auth.exceptions import WrongUsageError
from uobtheatre.graphql_auth.models import UserStatus
from uobtheatre.graphql_auth.constants import TokenAction
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_models_str_and_secondary_email_guard_errors():
    user = UserFactory()
    status = user.status

    assert str(status) == f"{user} - status"

    status.secondary_email = None
    with pytest.raises(WrongUsageError):
        status.swap_emails()

    with pytest.raises(WrongUsageError):
        status.remove_secondary_email()


@pytest.mark.django_db
def test_models_branches_for_clean_email_archive_and_unarchive():
    user = UserFactory()

    # clean_email with falsy value should no-op
    assert UserStatus.clean_email(False) is None

    status = user.status
    status.archived = False
    status.save(update_fields=["archived"])
    UserStatus.unarchive(user)
    status.refresh_from_db()
    assert status.archived is False

    status.archived = True
    status.save(update_fields=["archived"])
    UserStatus.archive(user)
    status.refresh_from_db()
    assert status.archived is True


@pytest.mark.django_db
def test_send_activation_email_delegates_with_activation_path():
    status = UserFactory().status
    request = SimpleNamespace(
        get_port=lambda: 443,
        is_secure=lambda: False,
    )
    info = SimpleNamespace(context=request)

    with mock.patch(
        "uobtheatre.graphql_auth.models.get_current_site",
        return_value=SimpleNamespace(name="Example", domain="example.com"),
    ), mock.patch(
        "uobtheatre.graphql_auth.models.get_token",
        return_value="token-1",
    ), mock.patch(
        "uobtheatre.graphql_auth.models.render_to_string",
        side_effect=[" Subject\n", "<p>Body</p>"],
    ), mock.patch(
        "uobtheatre.graphql_auth.models.strip_tags",
        return_value="Body",
    ), mock.patch(
        "uobtheatre.graphql_auth.models.send_mail",
        return_value=1,
    ) as send_mail:
        result = status.send_activation_email(info=info)

    assert result == 1
    send_mail.assert_called_once()


@pytest.mark.django_db
def test_get_email_context_uses_https_protocol_when_request_is_secure():
    status = UserFactory().status
    request = SimpleNamespace(
        get_port=lambda: 443,
        is_secure=lambda: True,
    )
    info = SimpleNamespace(context=request)

    with mock.patch(
        "uobtheatre.graphql_auth.models.get_current_site",
        return_value=SimpleNamespace(name="Example", domain="example.com"),
    ), mock.patch(
        "uobtheatre.graphql_auth.models.get_token",
        return_value="token-1",
    ):
        context = status.get_email_context(
            info,
            "/activate/",
            TokenAction.ACTIVATION,
        )

    assert context["protocol"] == "https"
    assert context["token"] == "token-1"
