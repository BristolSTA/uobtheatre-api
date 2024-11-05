import datetime

import pytest

from uobtheatre.site_messages.test.factories import SiteMessageFactory


@pytest.mark.django_db
def test_str_siteMessage():
    siteMessage = SiteMessageFactory()

    assert str(siteMessage) == "Site {0} (Event {1} until {2})".format(
        siteMessage.type.title(),
        siteMessage.event_start.strftime("%d/%m/%Y"),
        siteMessage.event_end.strftime("%d/%m/%Y"),
    )
