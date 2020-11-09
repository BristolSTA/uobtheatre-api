import factory

from uobtheatre.productions.models import (
    Society,
    Production,
)


class SocietyFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=3)

    class Meta:
        model = Society


class ProductionFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=3)
    society = factory.SubFactory(SocietyFactory)

    class Meta:
        model = Production
