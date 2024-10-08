from typing import Callable, Optional

from django import forms
from django.core.exceptions import ValidationError
from django.forms.fields import FileField
from django.forms.models import ModelForm
from django_tiptap.fields import TipTapTextFormField

from uobtheatre.mail.composer import MailComposer, MassMailComposer
from uobtheatre.users.models import User


class SendEmailForm(forms.Form):
    """
    Form for sending emails
    """

    subject = forms.CharField(label="Subject", required=True, min_length=5)
    users = forms.ModelMultipleChoiceField(queryset=User.objects.all(), required=True)
    # The first line in the email. Expalins why the user is receiving the email
    user_reason = forms.CharField(
        label="Reason",
        help_text="e.g. You are recieving this email because...",
        widget=forms.Textarea,
    )
    message = TipTapTextFormField(label="Message", required=True, min_length=5)
    lgtm = forms.BooleanField(
        label="Ready to send?",
        required=True,
    )

    # A function to generate the preface for the email. This overrides the
    # user_reason field.
    user_reason_generator: Optional[Callable[[User], str]] = None

    def submit(self):
        """Submit the form"""
        if not self.is_valid():
            raise ValidationError("You cannot submit an invalid form")

        mail = MailComposer().greeting()
        if preface := self.cleaned_data.get("user_reason"):
            mail.line(preface).rule()
        mail.html(self.cleaned_data["message"]).rule()

        MassMailComposer(
            self.cleaned_data["users"],
            subject=self.cleaned_data["subject"],
            mail_compose=mail,
        ).send_async()


class MutationForm(ModelForm):
    """The base form for mutation operations"""

    def __init__(self, *args, user: Optional[User] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if len(self.data.keys()) == 0 or "id" in self.data:
            for key, _ in list(self.fields.items()):
                self.fields[key].required = False

    def _clean_fields(self):
        """Overwrites the default clean_fields function of Django forms (uses initial data if field name not in provided data)"""
        for name, field in self.fields.items():
            if (
                field.disabled or not name in self.data
            ):  # Modified from base form on this line only
                value = self.get_initial_for_field(field, name)
            else:
                value = field.widget.value_from_datadict(
                    self.data, self.files, self.add_prefix(name)
                )
            try:  # pragma: no cover
                if isinstance(field, FileField):
                    initial = self.get_initial_for_field(field, name)
                    value = field.clean(value, initial)
                else:
                    value = field.clean(value)
                self.cleaned_data[name] = value
                if hasattr(self, "clean_%s" % name):
                    value = getattr(self, "clean_%s" % name)()
                    self.cleaned_data[name] = value
            except ValidationError as error:
                self.add_error(name, error)

    @property
    def is_creation(self):
        return not bool(self.instance.pk)

    # pylint: disable=useless-parent-delegation
    def _save_m2m(self):
        # This "useless" function is required to stop mypy from squawking about this class not having this function in child classes
        super()._save_m2m()  # type: ignore[misc]

    class Meta:
        abstract = True
