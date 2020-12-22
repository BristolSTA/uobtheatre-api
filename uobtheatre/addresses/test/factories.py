import factory

from uobtheatre.addresses.models import Address


class AddressFactory(factory.django.DjangoModelFactory):

    street = factory.Faker("street_name")
    city = factory.Faker("city")
    postcode = factory.Faker("postcode", locale="en_GB")
    latitude = factory.Faker("latitude")
    longitude = factory.Faker("longitude")

    class Meta:
        model = Address
