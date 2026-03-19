import importlib
import types
import uuid
from types import SimpleNamespace
from unittest import mock

import graphene
import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.core.signing import SignatureExpired
from graphene import NonNull
from graphql_jwt.exceptions import JSONWebTokenError

from uobtheatre.graphql_auth import mixins, mutations, relay, shortcuts
from uobtheatre.graphql_auth.backends import GraphQLAuthBackend
from uobtheatre.graphql_auth.bases import (
    DynamicArgsMixin,
    DynamicInputMixin,
    MutationMixin,
    RelayMutationMixin,
)
from uobtheatre.graphql_auth.connection import CountableConnection
from uobtheatre.graphql_auth.constants import TokenAction
from uobtheatre.graphql_auth.exceptions import WrongUsageError
from uobtheatre.graphql_auth.forms import PasswordLessRegisterForm
from uobtheatre.graphql_auth.models import UserStatus
from uobtheatre.graphql_auth.queries import MeQuery, UserNode, UserQuery
from uobtheatre.graphql_auth.settings import (
    GraphQLAuthSettings,
    reload_graphql_auth_settings,
)
from uobtheatre.graphql_auth.test import decorators as test_decorators
from uobtheatre.graphql_auth.types import ExpectedErrorType
from uobtheatre.graphql_auth.utils import (
    get_classes,
    get_token,
    get_token_payload,
)
from uobtheatre.users.test.factories import UserFactory


class _ParentMutation:
    @classmethod
    def mutate(cls, root, info, **kwargs):
        return {"called": "parent_mutate", **kwargs}


class _ChildMutation(MutationMixin, _ParentMutation):
    @classmethod
    def resolve_mutation(cls, root, info, **kwargs):
        return {"called": "resolve_mutation", **kwargs}


class _ParentRelayMutation:
    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        return {"called": "parent_payload", **kwargs}


class _ChildRelayMutation(RelayMutationMixin, _ParentRelayMutation):
    @classmethod
    def resolve_mutation(cls, root, info, **kwargs):
        return {"called": "resolve_payload", **kwargs}


class _DynamicArgsDictMutation(DynamicArgsMixin, graphene.Mutation):
    class Arguments:
        pass

    ok = graphene.Boolean()
    _args = {"nickname": "String"}
    _required_args = {"age": "Int"}

    @classmethod
    def mutate(cls, root, info, **kwargs):
        return cls(ok=True)


class _DynamicArgsListMutation(DynamicArgsMixin, graphene.Mutation):
    class Arguments:
        pass

    ok = graphene.Boolean()
    _args = ["nickname"]
    _required_args = ["age"]

    @classmethod
    def mutate(cls, root, info, **kwargs):
        return cls(ok=True)


class _DynamicInputDictMutation(DynamicInputMixin, graphene.ClientIDMutation):
    class Input:
        pass

    ok = graphene.Boolean()
    _inputs = {"nickname": "String"}
    _required_inputs = {"age": "Int"}

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        return cls(ok=True)


class _DynamicInputListMutation(DynamicInputMixin, graphene.ClientIDMutation):
    class Input:
        pass

    ok = graphene.Boolean()
    _inputs = ["nickname"]
    _required_inputs = ["age"]

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        return cls(ok=True)


def test_mutation_mixins_delegate_to_resolvers_and_parent_methods():
    assert _ChildMutation.mutate(None, None, value=1) == {
        "called": "resolve_mutation",
        "value": 1,
    }
    assert _ChildMutation.parent_resolve(None, None, value=2) == {
        "called": "parent_mutate",
        "value": 2,
    }

    assert _ChildRelayMutation.mutate_and_get_payload(None, None, value=3) == {
        "called": "resolve_payload",
        "value": 3,
    }
    assert _ChildRelayMutation.parent_resolve(None, None, value=4) == {
        "called": "parent_payload",
        "value": 4,
    }


def test_dynamic_mixins_populate_args_and_input_fields():
    _DynamicArgsDictMutation.Field()
    _DynamicArgsListMutation.Field()

    args_dict = _DynamicArgsDictMutation._meta.arguments
    assert "nickname" in args_dict
    assert "age" in args_dict
    assert isinstance(args_dict["age"].type, NonNull)

    args_list = _DynamicArgsListMutation._meta.arguments
    assert "nickname" in args_list
    assert "age" in args_list

    _DynamicInputDictMutation.Field()
    _DynamicInputListMutation.Field()

    input_dict = _DynamicInputDictMutation._meta.arguments[
        "input"
    ]._meta.fields
    assert "nickname" in input_dict
    assert "age" in input_dict

    input_list = _DynamicInputListMutation._meta.arguments[
        "input"
    ]._meta.fields
    assert "nickname" in input_list
    assert "age" in input_list


def test_dynamic_mixins_handle_non_list_non_dict_inputs():
    class ArgsOther(DynamicArgsMixin, graphene.Mutation):
        class Arguments:
            pass

        ok = graphene.Boolean()
        _args = ("tuple",)
        _required_args = ("tuple",)

        @classmethod
        def mutate(cls, root, info, **kwargs):
            return cls(ok=True)

    class InputOther(DynamicInputMixin, graphene.ClientIDMutation):
        class Input:
            pass

        ok = graphene.Boolean()
        _inputs = ("tuple",)
        _required_inputs = ("tuple",)

        @classmethod
        def mutate_and_get_payload(cls, root, info, **kwargs):
            return cls(ok=True)

    assert ArgsOther.Field() is not None
    assert InputOther.Field() is not None


def test_connection_resolve_total_count_uses_iterable_count():
    connection = CountableConnection.__new__(CountableConnection)
    connection.iterable = mock.Mock()
    connection.iterable.count.return_value = 7

    assert connection.resolve_total_count(info=None) == 7


def test_settings_constructor_accepts_explicit_user_settings():
    settings = GraphQLAuthSettings(
        user_settings={"ALLOW_LOGIN_NOT_VERIFIED": False},
        defaults={"ALLOW_LOGIN_NOT_VERIFIED": True},
    )

    assert settings._user_settings["ALLOW_LOGIN_NOT_VERIFIED"] is False
    assert settings.ALLOW_LOGIN_NOT_VERIFIED is False


def test_expected_error_type_serialize_branches():
    result = ExpectedErrorType.serialize(
        {"__all__": [{"message": "oops", "code": "x"}]}
    )
    assert "nonFieldErrors" in result

    list_result = ExpectedErrorType.serialize(
        [{"message": "invalid", "code": "y"}]
    )
    assert list_result == {
        "nonFieldErrors": [{"message": "invalid", "code": "y"}]
    }

    with pytest.raises(WrongUsageError):
        ExpectedErrorType.serialize("not-a-valid-errors-shape")

    dict_result = ExpectedErrorType.serialize(
        {"email": [{"message": "taken", "code": "taken"}]}
    )
    assert "email" in dict_result


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
def test_shortcuts_cover_custom_type_async_and_username_login_paths():
    user = UserFactory()
    assert shortcuts.get_user_to_login(id=user.id).id == user.id

    reload_graphql_auth_settings(
        setting="GRAPHQL_AUTH",
        value={
            "EMAIL_ASYNC_TASK": "uobtheatre.graphql_auth.shortcuts.get_output_error_type"
        },
    )
    try:
        async_func = shortcuts.get_async_email_func()
    finally:
        reload_graphql_auth_settings(setting="GRAPHQL_AUTH", value={})
    assert callable(async_func)

    with mock.patch.object(
        shortcuts.app_settings,
        "CUSTOM_ERROR_TYPE",
        "uobtheatre.graphql_auth.types.ExpectedErrorType",
    ):
        assert shortcuts.get_output_error_type() is ExpectedErrorType

    with pytest.raises(ObjectDoesNotExist):
        shortcuts.get_user_to_login(id=uuid.uuid4())


def test_utils_get_token_handles_pk_username_and_get_classes_no_filter():
    class UsernameWithPk:
        pk = 42

    class DummyUser:
        USERNAME_FIELD = "email"
        email = "example@example.com"

        def get_username(self):
            return UsernameWithPk()

    token = get_token(DummyUser(), TokenAction.ACTIVATION)
    payload = get_token_payload(token, TokenAction.ACTIVATION)
    assert payload["email"] == 42

    module = types.ModuleType("temp_module")

    class Alpha:
        pass

    module.Alpha = Alpha
    classes = get_classes(module)
    assert ("Alpha", Alpha) in classes

    imported_classes = get_classes("uobtheatre.graphql_auth.utils")
    assert any(name == "TokenScopeError" for name, _ in imported_classes)


@pytest.mark.django_db
def test_query_resolvers_cover_staff_and_anonymous_paths():
    staff_user = UserFactory(is_staff=True)
    regular_user = UserFactory(is_staff=False)

    info_staff = SimpleNamespace(context=SimpleNamespace(user=staff_user))
    info_regular = SimpleNamespace(context=SimpleNamespace(user=regular_user))
    anonymous_user = SimpleNamespace(is_authenticated=False, is_staff=False)
    info_anon = SimpleNamespace(context=SimpleNamespace(user=anonymous_user))

    with mock.patch(
        "graphene_django.types.DjangoObjectType.get_node",
        return_value="node",
    ):
        assert UserNode.get_node(info_staff, 1) == "node"
    assert UserNode.get_node(info_regular, 1) is None

    queryset = UserNode.get_queryset(
        UserFactory._meta.model.objects.all(), info_staff
    )
    assert queryset is not None

    assert UserNode.resolve_pk(staff_user, info_staff) == staff_user.pk
    assert UserNode.resolve_archived(staff_user, info_staff) is False
    assert UserNode.resolve_verified(staff_user, info_staff) is False
    assert UserNode.resolve_secondary_email(staff_user, info_staff) is None

    query = UserQuery()
    assert query.resolve_users(info_staff).count() >= 1
    assert query.resolve_users(info_regular).count() == 0

    me_query = MeQuery()
    assert me_query.resolve_me(info_staff).id == staff_user.id
    assert me_query.resolve_me(info_anon) is None


def test_relay_and_mutations_field_helpers_exercise_token_branches():
    importlib.reload(relay)
    importlib.reload(mutations)

    with mock.patch.object(
        relay.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", False
    ), mock.patch.object(
        relay.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", True
    ):
        relay.ObtainJSONWebToken.Field()
        relay.RefreshToken.Field()

    with mock.patch.object(
        relay.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", True
    ), mock.patch.object(
        relay.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", False
    ):
        relay.ObtainJSONWebToken.Field()
        relay.RefreshToken.Field()

    with mock.patch.object(
        mutations.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", False
    ), mock.patch.object(
        mutations.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", True
    ):
        mutations.ObtainJSONWebToken.Field()
        mutations.RefreshToken.Field()

    with mock.patch.object(
        mutations.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", True
    ), mock.patch.object(
        mutations.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", False
    ):
        mutations.ObtainJSONWebToken.Field()
        mutations.RefreshToken.Field()

    with mock.patch.object(
        mutations.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", False
    ), mock.patch.object(
        mutations.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", False
    ):
        mutations.ObtainJSONWebToken.Field()
        mutations.RefreshToken.Field()

    with mock.patch.object(
        relay.jwt_settings, "JWT_HIDE_TOKEN_FIELDS", False
    ), mock.patch.object(
        relay.jwt_settings, "JWT_LONG_RUNNING_REFRESH_TOKEN", False
    ):
        relay.ObtainJSONWebToken.Field()
        relay.RefreshToken.Field()


def test_backend_authenticate_handles_jwt_errors_gracefully():
    request = SimpleNamespace(_jwt_token_auth=False)
    backend = GraphQLAuthBackend()

    with mock.patch(
        "uobtheatre.graphql_auth.backends.get_credentials",
        return_value="jwt-token",
    ), mock.patch(
        "uobtheatre.graphql_auth.backends.get_user_by_token",
        side_effect=JSONWebTokenError("invalid"),
    ):
        assert backend.authenticate(request=request) is None

    with mock.patch(
        "uobtheatre.graphql_auth.backends.get_credentials",
        return_value=None,
    ):
        assert backend.authenticate(request=request) is None


@pytest.mark.django_db
def test_passwordless_register_form_sets_optional_password_and_saves():
    form = PasswordLessRegisterForm(
        {
            "email": "passwordless@example.com",
            "password1": "",
            "password2": "",
        }
    )
    assert form.fields["password1"].required is False
    assert form.fields["password2"].required is False
    assert form.is_valid()

    user = form.save(commit=True)
    assert user.has_usable_password() is False

    other = form.save(commit=False)
    assert other.has_usable_password() is False


def test_graphql_auth_test_decorator_helper_returns_skipif_mark():
    mark = test_decorators.skipif_django_21()
    assert mark.mark.name == "skipif"


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


@pytest.mark.django_db
def test_shortcuts_login_email_branch_without_secondary_email(monkeypatch):
    user = UserFactory(email="primary-only@example.com")
    monkeypatch.setattr(
        shortcuts.app_settings,
        "ALLOW_LOGIN_WITH_SECONDARY_EMAIL",
        False,
    )
    found = shortcuts.get_user_to_login(email="primary-only@example.com")
    assert found.id == user.id
