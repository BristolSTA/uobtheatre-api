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
    event_end = factory.Faker(
        "future_datetime", tzinfo=timezone.get_current_timezone()
    )
    user = factory.SubFactory(UserFactory)
    type = factory.Faker(
        "random_element", elements=[x[0] for x in Message.Type.choices]
    )
    dismissal_policy = factory.Faker(
        "random_element", elements=[x[0] for x in Message.Policy.choices]
    )
    display_location = factory.Faker(
        "random_element",
        elements=[x[0] for x in Message.DisplayLocation.choices],
    )
    title = factory.Faker("sentence", nb_words=3)

    class Meta:
        model = Message


def create_site_message(
    display_start,
    event_start,
    event_end,
    message_id,
    indefinite_override=False,
    active=True,
):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """
    Create a site message with given timing information to test ordering

    Args:
        display_start (datetime): The time the message should start displaying
        event_start (datetime): The time the event starts
        event_end (datetime): The time the event ends
        message_id (int): The ID to assign to the message
        indefinite_override (bool): Whether the message should ignore the event_end time and continue to display indefinitely.
        active (bool): Whether the message is active.

    Returns:
        message: The generated Site Message.
    """
    message = SiteMessageFactory(
        display_start=display_start,
        event_start=event_start,
        event_end=event_end,
        id=message_id,
        indefinite_override=indefinite_override,
        active=active,
    )
    return message
