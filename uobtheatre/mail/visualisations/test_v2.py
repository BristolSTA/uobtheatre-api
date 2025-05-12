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
        MailComposer()
        .colStack([
                (Spacer(), 5),
                (RowStack([
                    Logo(),
                    Spacer(height=15),
                    Box(
                        Paragraph("This is a test title", "This is a test message that's actually longer than you would expect it to be because it's important for the sake of testing that we have a really long message here that spans multiple lines."),
                        bgCol="#ffffff"),
                    Spacer(height=50),
                    Button("example.org", "Take Me to Example.Org!")
                ]), 90),
            (Spacer(), 5)
        ])
    )

    write_html_file(test_mail, "simple_email.html")
