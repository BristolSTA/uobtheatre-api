import factory

from uobtheatre.societies.models import (
    Society,
)


class SocietyFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)

    class Meta:
        model = Society
