import factory

from uobtheatre.societies.models import Society


class SocietyFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("sentence", nb_words=20)
    logo = factory.django.ImageField(color="blue", use_url=True)
    banner = factory.django.ImageField(color="blue", use_url=True)

    class Meta:
        model = Society
