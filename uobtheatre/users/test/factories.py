import uuid

import factory
from django.contrib.auth.models import Group
from uobtheatre.users.models import User


class GroupFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("sentence", nb_words=2)

    class Meta:
        model = Group


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save=True

    id = factory.LazyFunction(uuid.uuid4)
    password = factory.Faker(
        "password",
        length=10,
        special_chars=True,
        digits=True,
        upper_case=True,
        lower_case=True,
    )
    email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False

    @factory.post_generation
    def groups(self, _, extracted):
        """Handle user group adding on create"""
        if extracted:
            for group in extracted:
                self.groups.add(group)
                group.save()
                self.save()
