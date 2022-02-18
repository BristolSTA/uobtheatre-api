import pytest

from uobtheatre.mail.tasks import send_emails


@pytest.mark.django_db
def test_send_emails_task(mailoutbox):

    emails = [
        {
            "subject": "Subject",
            "plain_text": "Yes",
            "html": "<p>Yes!</p>",
            "addresses": ["joe@example.org"],
        },
        {
            "subject": "Subject",
            "plain_text": "Yes",
            "html": "<p>Yes!</p>",
            "addresses": ["jill@example.org"],
        },
    ]

    send_emails(emails)

    assert len(mailoutbox) == 3
    assert mailoutbox[0].subject == "Subject"
    assert "Yes" in mailoutbox[0].body
    assert mailoutbox[0].to == ["joe@example.org"]
    assert mailoutbox[1].to == ["jill@example.org"]
    assert mailoutbox[2].to == ["webmaster@bristolsta.com"]
    assert mailoutbox[2].subject == "[UOBTheatre] Mass Email Sent: Subject"
