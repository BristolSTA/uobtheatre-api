# Use pytest functionality to generate HTML emails in the visualisations folder for generation

import pytest
import os

import factory
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.utils.lang import pluralize

from uobtheatre.mail.composerV2 import *

root = "./uobtheatre/mail/visualisations/v2/"

mountainImage = "https://media.gettyimages.com/id/1211045588/photo/beautiful-winter-mountain-landscape-with-snow-and-glacier-lake.jpg?b=1&s=1024x1024&w=gi&k=20&c=gjiSUA2OVP3s8zJkmJDsBL2V80Hprvjdv5ZdEkV3VuE="


def write_html_file(mail, filename):
    # Delete the existing file
    if not os.path.exists(root + filename):
        with open(root + filename, "x") as f:
            f.write(mail.to_html())
    else:
        with open(root + filename, "w") as f:
            f.write(mail.to_html())


@pytest.mark.django_db
def test_simple_email():

    test_mail = (
        MailComposer.blank([Box(
            Paragraph("This is a test title", "This is a test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines."),
            bgCol="#ffffff"),
            Box(
            Paragraph(title="This is a new test title"),
            bgCol="#ffffff"),
            Box(
            Paragraph(message="This is a new test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines."),
            bgCol="#ffffff")]
        ))

    write_html_file(test_mail, "simple_email.html")


@pytest.mark.django_db
def test_text_only():

    test_mail = MailComposer.textOnly(
        "This is a test title", "<b>This</b> is a test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines.", True)

    write_html_file(test_mail, "text_only.html")
