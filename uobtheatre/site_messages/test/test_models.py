import datetime

import pytest

from uobtheatre.site_messages.test.factories import SiteMessageFactory


@pytest.mark.django_db
def test_str_site_message():
    site_message = SiteMessageFactory()

    assert str(site_message) == "Site {0} (Event {1} until {2})".format(
        site_message.type.title(),
        site_message.event_start.strftime("%d/%m/%Y"),
        site_message.event_end.strftime("%d/%m/%Y"),
    )
