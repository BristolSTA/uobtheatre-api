import pytest

from uobtheatre.graphql_auth.forms import PasswordLessRegisterForm


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
