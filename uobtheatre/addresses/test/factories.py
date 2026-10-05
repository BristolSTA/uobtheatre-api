import factory

from uobtheatre.addresses.models import Address


class AddressFactory(factory.django.DjangoModelFactory):
    street = factory.Faker("street_name")
    building_name = factory.Faker("sentence", nb_words=2)
    building_number = factory.Faker("bothify", text="##")
    city = factory.Faker("city")
    postcode = factory.Faker("postcode", locale="en_GB")
    what3words = factory.Faker("bothify", text="??????.??????.??????")
    latitude = factory.Faker("latitude")
    longitude = factory.Faker("longitude")

    class Meta:
        model = Address
