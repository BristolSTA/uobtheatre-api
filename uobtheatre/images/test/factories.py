import factory

from uobtheatre.images.models import Image


class ImageFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=3)
    file = factory.django.ImageField(color="blue", use_url=True)

    class Meta:
        model = Image
