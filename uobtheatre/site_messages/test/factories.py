import factory
from django.utils import timezone

from uobtheatre.site_messages.models import Message
from uobtheatre.users.test.factories import UserFactory


class SiteMessageFactory(factory.django.DjangoModelFactory):
    message = factory.Faker("sentence", nb_words=15)
    active = factory.Faker("boolean")
    indefinite_override = factory.Faker("boolean")
    display_start = factory.Faker(
        "future_datetime", tzinfo=timezone.get_current_timezone()
    )
    event_start = factory.Faker(
        "future_datetime", tzinfo=timezone.get_current_timezone()
    )
    event_end = factory.Faker("future_datetime", tzinfo=timezone.get_current_timezone())
    creator = factory.SubFactory(UserFactory)
    type = factory.Faker(
        "random_element", elements=[x[0] for x in Message.Type.choices]
    )
    dismissal_policy = factory.Faker(
        "random_element", elements=[x[0] for x in Message.Policy.choices]
    )

    class Meta:
        model = Message


def create_site_message(display_start, event_start, event_end, id):
    """Create a site message with given timing information to test ordering
    Args:
        display_start (datetime)
        event_start (datetime)
        event_end (datetime)
        id (int)

    Returns:
        message: The generated Site Message.
    """
    message = SiteMessageFactory(
        display_start=display_start, event_start=event_start, event_end=event_end, id=id
    )
    return message
