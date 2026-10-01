import importlib
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.signing import SignatureExpired

from uobtheatre.graphql_auth import mixins


@pytest.mark.django_db
def test_mixins_cover_remaining_branches_with_mocks(monkeypatch):
    importlib.reload(mixins)

    class DummyOutput:
        _meta = SimpleNamespace(fields={"success": None, "token": None})

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class DummyRegister(mixins.RegisterMixin, DummyOutput):
        pass

    class DummyVerifySecondary(mixins.VerifySecondaryEmailMixin, DummyOutput):
        pass

    class DummyResend(mixins.ResendActivationEmailMixin, DummyOutput):
        pass

    class DummyPasswordReset(mixins.PasswordResetMixin, DummyOutput):
        pass

    class DummyPasswordSet(mixins.PasswordSetMixin, DummyOutput):
        pass

    class DummyTokenAuth(mixins.ObtainJSONWebTokenMixin, DummyOutput):
        @classmethod
        def parent_resolve(cls, root, info, **kwargs):
            return cls(success=True, **kwargs)

    fake_form = mock.Mock()
    fake_form.is_valid.return_value = True
    fake_form.errors.get_json_data.return_value = {"field": "error"}

    user = mock.Mock()
    user.status = mock.Mock(verified=False)

    monkeypatch.setattr(DummyRegister, "form", lambda _: fake_form)
    monkeypatch.setattr(mixins.UserStatus, "clean_email", mock.Mock())
    fake_form.save.return_value = user

    monkeypatch.setattr(mixins.app_settings, "SEND_ACTIVATION_EMAIL", True)
    monkeypatch.setattr(
        mixins.app_settings, "ALLOW_PASSWORDLESS_REGISTRATION", False
    )
    monkeypatch.setattr(mixins.app_settings, "SEND_PASSWORD_SET_EMAIL", False)
    monkeypatch.setattr(mixins.app_settings, "ALLOW_LOGIN_NOT_VERIFIED", True)
    monkeypatch.setattr(
        mixins.app_settings,
        "_is_declared_async_email",
        True,
        raising=False,
    )
    monkeypatch.setattr(mixins, "async_email_func", mock.Mock())
    wrapped = DummyRegister.login_on_register
    while hasattr(wrapped, "__wrapped__"):
        wrapped = wrapped.__wrapped__
    login_result = wrapped(DummyRegister, None, None)

    monkeypatch.setattr(
        DummyRegister,
        "login_on_register",
        mock.Mock(return_value=SimpleNamespace(success=True, token="jwt")),
    )
    result = DummyRegister.resolve_mutation(
        None,
        SimpleNamespace(context=SimpleNamespace()),
        email="person@example.com",
        password1="pw",
    )
    assert result.success is True
    assert result.token == "jwt"

    assert isinstance(login_result, DummyRegister)

    with mock.patch.object(
        mixins.UserStatus,
        "verify_secondary_email",
        side_effect=SignatureExpired(),
    ):
        verify_result = DummyVerifySecondary.resolve_mutation(
            None,
            None,
            token="x",
        )
    assert verify_result.success is False

    monkeypatch.setattr(
        mixins, "get_user_by_email", mock.Mock(return_value=user)
    )
    monkeypatch.setattr(mixins, "async_email_func", mock.Mock())
    resend_result = DummyResend.resolve_mutation(
        None, None, email="person@example.com"
    )
    assert resend_result.success is True

    reset_form = mock.Mock()
    reset_form.is_valid.return_value = True
    reset_form.save.return_value = user
    monkeypatch.setattr(
        DummyPasswordReset, "form", lambda _user, _kwargs: reset_form
    )
    monkeypatch.setattr(
        mixins,
        "get_token_payload",
        mock.Mock(return_value={"email": "person@example.com"}),
    )
    monkeypatch.setattr(
        mixins.UserModel._default_manager, "get", mock.Mock(return_value=user)
    )
    monkeypatch.setattr(mixins, "revoke_user_refresh_token", mock.Mock())
    reset_result = DummyPasswordReset.resolve_mutation(
        None,
        None,
        token="reset-token",
        new_password1="abc12345",
        new_password2="abc12345",
    )
    assert reset_result.success is True
    assert user.status.save.called

    monkeypatch.setattr(
        mixins,
        "get_token_payload",
        mock.Mock(side_effect=SignatureExpired()),
    )
    expired_reset = DummyPasswordReset.resolve_mutation(
        None,
        None,
        token="expired-token",
        new_password1="abc12345",
        new_password2="abc12345",
    )
    assert expired_reset.success is False

    user.status.verified = False
    user.has_usable_password.return_value = False
    set_form = mock.Mock()
    set_form.is_valid.return_value = True
    set_form.save.return_value = user
    monkeypatch.setattr(
        mixins,
        "get_token_payload",
        mock.Mock(return_value={"email": "person@example.com"}),
    )
    monkeypatch.setattr(
        DummyPasswordSet, "form", lambda _user, _kwargs: set_form
    )
    set_result = DummyPasswordSet.resolve_mutation(
        None,
        None,
        token="set-token",
        new_password1="abc12345",
        new_password2="abc12345",
    )
    assert set_result.success is True

    user_to_login = mock.Mock()
    user_to_login.status = mock.Mock(verified=True)
    setattr(
        user_to_login, mixins.UserModel.USERNAME_FIELD, "person@example.com"
    )
    monkeypatch.setattr(
        mixins,
        "get_user_to_login",
        mock.Mock(return_value=user_to_login),
    )
    token_result = DummyTokenAuth.resolve_mutation(
        None,
        None,
        password="pw",
        username="person",
    )
    assert token_result.success is True

    # Reload with no refresh tokens to exercise class-level false branches.
    with mock.patch(
        "uobtheatre.graphql_auth.utils.using_refresh_tokens",
        return_value=False,
    ):
        importlib.reload(mixins)
