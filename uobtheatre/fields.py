from django.db import models
from django.forms import fields
from django_tiptap_editor.widgets.tiptap_widget import TipTapWidget


class TipTapTextFormField(fields.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.update({"widget": TipTapWidget()})
        super().__init__(*args, **kwargs)


class TipTapTextField(models.TextField):
    def formfield(self, **kwargs):  # type: ignore[override]
        return super().formfield(form_class=TipTapTextFormField, **kwargs)
