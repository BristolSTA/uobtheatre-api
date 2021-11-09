from django.core.exceptions import ValidationError
from django.forms.models import ModelForm
from factory.django import FileField


class MutationForm(ModelForm):
    """The base form for mutation operations"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if len(self.data.keys()) == 0 or "id" in self.data:
            for (key, _) in list(self.fields.items()):
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

    class Meta:
        abstract = True
