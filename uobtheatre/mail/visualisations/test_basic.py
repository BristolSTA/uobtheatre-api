# Use pytest functionality to generate HTML emails in the visualisations folder for generation

import pytest
import os

from uobtheatre.mail.composer import (MailComposer)

root = "./uobtheatre/mail/visualisations/basic/"


@pytest.mark.django_db
def test_simple_email():

    htmlPath = root + "simple_email.html"

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

    # Delete the existing file
    if not os.path.exists(htmlPath):
        with open(htmlPath, "x") as f:
            f.write(test_mail.to_html())
    else:
        with open(htmlPath, "w") as f:
            f.write(test_mail.to_html())
