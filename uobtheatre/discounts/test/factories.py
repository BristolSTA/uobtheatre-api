import factory

from uobtheatre.discounts.models import ConcessionType, Discount, DiscountRequirement


class DiscountFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)
    percentage = 0.2

    class Meta:
        model = Discount


class ConcessionTypeFactory(factory.django.DjangoModelFactory):

    name = factory.Faker("sentence", nb_words=2)

    class Meta:
        model = ConcessionType


class DiscountRequirementFactory(factory.django.DjangoModelFactory):

    number = 1
    concession_type = factory.SubFactory(ConcessionTypeFactory)

    class Meta:
        model = DiscountRequirement
