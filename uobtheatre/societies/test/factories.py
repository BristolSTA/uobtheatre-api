import factory

from uobtheatre.images.test.factories import ImageFactory
from uobtheatre.societies.models import Society


class SocietyFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("sentence", nb_words=20)
    logo = factory.SubFactory(ImageFactory)
    banner = factory.SubFactory(ImageFactory)

    class Meta:
        model = Society
