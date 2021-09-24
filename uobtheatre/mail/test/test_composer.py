import importlib.resources as pkg_resources

import fixtures
import pytest
from django.template.loader import get_template

from uobtheatre.mail.composer import Action, Heading, Image, Line, MailComposer


def test_it_generates_correct_plain_text():
    composer = (
        MailComposer()
        .heading("This is a heading")
        .line("This is a paragraph")
        .image("http://example.org/my/image")
        .line("This is another paragraph")
        .action("https://example.org/call/to/action", "Call to Action")
        .line("This is the final paragraph")
    )

    assert composer.to_plain_text() == pkg_resources.read_text(
        fixtures, "plain_text.txt"
    )


@pytest.mark.django_db
def test_it_generates_correct_html():
    composer = (
        MailComposer()
        .heading("This is a heading")
        .line("This is a paragraph")
        .image("http://example.org/my/image")
        .line("This is another paragraph")
        .action("https://example.org/call/to/action", "Call to Action")
        .line("This is the final paragraph")
    )

    assert Heading("This is a heading").to_html() in composer.to_html()
    assert Line("This is a paragraph").to_html() in composer.to_html()
    assert Image("http://example.org/my/image").to_html() in composer.to_html()
    assert (
        Action("https://example.org/call/to/action", "Call to Action").to_html()
        in composer.to_html()
    )


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


@pytest.mark.parametrize("size", [1, 2, 3])
def test_heading_item(size):
    heading = Heading("My Heading %s" % size, size)
    assert heading.to_text() == "My Heading %s" % size
    assert heading.to_html() == "<h%s>My Heading %s</h%s>" % (size, size, size)
