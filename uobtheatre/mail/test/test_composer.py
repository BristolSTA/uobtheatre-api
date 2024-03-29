import importlib.resources as pkg_resources
from unittest.mock import patch

import pytest
from django.template.loader import get_template

from uobtheatre.mail.composer import (
    Action,
    Heading,
    Html,
    Image,
    Line,
    MailComposer,
    MassMailComposer,
    Panel,
    Rule,
)
from uobtheatre.mail.test import fixtures
from uobtheatre.users.test.factories import UserFactory

test_mail = (
    MailComposer()
    .heading("This is a heading")
    .line("This is a paragraph")
    .rule()
    .html("<b>Bold!</b>")
    .image("http://example.org/my/image")
    .line("This is another paragraph")
    .action("https://example.org/call/to/action", "Call to Action")
    .line("This is the final paragraph")
)


def test_it_generates_correct_plain_text():
    assert test_mail.to_plain_text() == pkg_resources.read_text(
        fixtures, "plain_text.txt"
    )


@pytest.mark.django_db
def test_it_generates_correct_html():
    assert ">This is a heading</h1>" in test_mail.to_html()
    assert ">This is a paragraph</p>" in test_mail.to_html()
    assert "<hr/>" in test_mail.to_html()
    assert "<b>Bold!</b>" in test_mail.to_html()
    assert Image("http://example.org/my/image").to_html() in test_mail.to_html()
    assert 'href="https://example.org/call/to/action"' in test_mail.to_html()
    assert ">Call to Action</a>" in test_mail.to_html()


@pytest.mark.django_db
def test_it_can_send(mailoutbox):
    composer = (
        MailComposer()
        .heading("This is a heading")
        .line("This is a paragraph")
        .image("http://example.org/my/image")
        .line("This is another paragraph")
        .action("https://example.org/call/to/action", "Call to Action")
        .line("This is the final paragraph")
    )

    composer.send("Email Subject", "joe@example.org")

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.subject == "Email Subject"
    assert email.to == ["joe@example.org"]
    assert email.body == composer.to_plain_text()
    assert email.alternatives[0][0] == composer.to_html()
    assert email.alternatives[0][1] == "text/html"


def test_line_item():
    line = Line("My paragraph text")
    assert line.to_html() == "<p>My paragraph text</p>"
    assert line.to_text() == "My paragraph text"


def test_html_item():
    html = Html("<div>My Text<p>Another Line</p></div>")
    assert html.to_html() == "<div>My Text<p>Another Line</p></div>"
    assert html.to_text() == "My Text\n\nAnother Line\n\n"


def test_rule_item():
    rule = Rule()
    assert rule.to_html() == "<p><hr /></p>"
    assert rule.to_text() == "---------"


def test_line_item_with_html():
    line = Line("My <strong>strong</strong> paragraph text")
    assert line.to_html() == "<p>My <strong>strong</strong> paragraph text</p>"
    assert line.to_text() == "My strong paragraph text"


def test_image_item():
    image = Image("http://example.org/my/image")

    assert image.to_html() == get_template("components/image.html").render(
        {"url": "http://example.org/my/image"}
    )
    assert image.to_text() is None


def test_action_item():
    action = Action("http://example.org/call/to/action", "Call to Action")

    assert action.to_html() == get_template("components/button.html").render(
        {"url": "http://example.org/call/to/action", "text": "Call to Action"}
    )
    assert action.to_text() == "Call to Action (http://example.org/call/to/action)"


def test_panel_item():
    panel = Panel()
    panel.line("Test text")

    assert panel.to_text() == "Test text"
    assert panel.to_html() == get_template("components/panel.html").render(
        {"content": Line("Test text").to_html()}
    )


def test_append():
    line = Line("Test")
    composer = MailComposer()
    assert not composer.items
    composer.append(line)
    assert composer.items == [line]


@pytest.mark.django_db
@pytest.mark.parametrize("with_user,expected", [(True, "Hi Test"), (False, "Hello")])
def test_greeting(with_user, expected):
    composer = MailComposer()
    user = UserFactory(first_name="Test")
    user.status.verified = True

    assert not composer.items
    composer.greeting(user if with_user else None)
    assert isinstance(composer.items[0], Heading) is True
    assert composer.items[0].text == expected


@pytest.mark.parametrize("size", [1, 2, 3])
def test_heading_item(size):
    heading = Heading("My Heading %s" % size, size)
    assert heading.to_text() == "My Heading %s" % size
    assert heading.to_html() == "<h%s>My Heading %s</h%s>" % (size, size, size)


@pytest.mark.django_db
def test_mass_mail_composer():
    mass_mail = MassMailComposer(
        [UserFactory(email="joe@example.org"), UserFactory(email="jill@example.org")],
        "My Subject",
        mail_compose=MailComposer().greeting().line("Test"),
    )

    with patch("uobtheatre.mail.tasks.send_emails.delay") as mock:
        mass_mail.send_async()

    mock.assert_called_once()

    args = mock.call_args[0]
    assert args[0] == ["joe@example.org", "jill@example.org"]
    assert args[1] == "My Subject"
    assert "Test" in args[2]
    assert "Test" in args[3]


@pytest.mark.django_db
def test_mass_mail_composer_no_users():
    mass_mail = MassMailComposer(
        [],
        "My Subject",
        mail_compose=MailComposer(),
    )

    with patch("uobtheatre.mail.tasks.send_emails.delay") as mock:
        mass_mail.send_async()
    mock.assert_not_called()
