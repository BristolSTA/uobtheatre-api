from django.forms import ModelForm, CharField
from uobtheatre.productions.models import Production


class UpdateForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for (key, _) in self.fields.items():
            self.fields[key].required = False

    class Meta:
        abstract = True


class CreateProductionForm(ModelForm):
    name = CharField(required=True)

    class Meta:
        model = Production
        fields = (
            "name",
            "subtitle",
            "description",
            "cover_image",
            "poster_image",
            "featured_image",
            "age_rating",
            "facebook_event",
            "warnings",
        )


class UpdateProductionForm(UpdateForm):
    class Meta:
        model = Production
        fields = (
            "name",
            "subtitle",
            "description",
            "cover_image",
            "poster_image",
            "featured_image",
            "age_rating",
            "facebook_event",
        )
