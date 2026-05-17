import importlib.resources as pkg_resources
from datetime import datetime
from unittest.mock import patch

import pytest
from django.template.loader import get_template

from uobtheatre.mail.composer_v2 import (
    QR,
    AccessibilityBlock,
    BookingBlock,
    Box,
    BoxCols,
    Button,
    ButtonHelpText,
    ColStack,
    ComposerItemInterface,
    Footer,
    Greeting,
    Heading,
    Image,
    ListItem,
    Logo,
    MailComposer,
    Paragraph,
    RowStack,
    Spacer,
    TicketCodes,
    TimingsBlock,
)
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
def test_greeting_block():
    user = UserFactory(first_name="Test")
    user.status.verified = True
    greeting = Greeting(user)
    assert "Hi Test" in greeting.to_text()
    assert "Hi Test" in greeting.to_html()
    generic = Greeting()
    assert "Hello" in generic.to_text()
    assert "Hello" in generic.to_html()


def test_paragraph():
    para = Paragraph("This is a paragraph.")
    assert para.to_text() == "This is a paragraph."
    assert "This is a paragraph." in para.to_html()


def test_heading():
    heading = Heading(
        title="Title",
        subtitle="Sub",
        subsubtitle="SubSub",
        message="Msg",
        title_icon="clock",
        message_icon="search",
    )
    text = heading.to_text()
    assert "Title" in text and "Sub" in text and "Msg" in text
    html = heading.to_html()
    assert "Title" in html and "Sub" in html and "Msg" in html


def test_list_item():
    item = ListItem(
        title="T", message="M", title_icon="clock", message_icon="search"
    )
    assert item.to_text() == "T: M"
    assert "T" in item.to_html() and "M" in item.to_html()


@pytest.mark.django_db
def test_button():
    btn = Button("/test", "Test Button")
    assert "Test Button" in btn.to_text()
    assert "/test" in btn.to_text()
    assert "Test Button" in btn.to_html()


def test_button_help_text():
    btn = ButtonHelpText("/test", "Test Button")
    assert "can't click".lower() in btn.to_text().lower()
    assert "Test Button" in btn.to_text()
    assert "/test" in btn.to_text()
    assert "Test Button" in btn.to_html()


def test_box_and_image():
    para = Paragraph("Boxed!")
    box = Box(para)
    assert "Boxed!" in box.to_text()
    assert "Boxed!" in box.to_html()
    img = Image("/img.png", alt="Alt", title="Title", href="/link")
    assert img.to_text() == "Alt"
    assert "img.png" in img.to_html()


def test_qr():
    qr = QR("test-content")
    assert "test-content" in qr.to_text()
    assert "svg" in qr.to_html().lower()


def test_ticket_codes():
    tc = TicketCodes("REF", ["T1", "T2"])
    text = tc.to_text()
    assert "ticket QR code" in text
    html = tc.to_html()
    assert "Ticket 1" in html and "Ticket 2" in html


@pytest.mark.django_db
def test_logo_footer():
    logo = Logo()
    assert "UOB Theatre" in logo.to_text()
    assert (
        "site_url" in logo.to_html() or "uobtheatre" in logo.to_html().lower()
    )
    footer = Footer()
    assert "Copyright" in footer.to_text()
    assert str(datetime.now().year) in footer.to_html()


def test_rowstack_colstack_spacer_boxcols():
    para1 = Paragraph("A")
    para2 = Paragraph("B")
    row = RowStack([para1, para2])
    assert "A" in row.to_text() and "B" in row.to_text()
    assert "A" in row.to_html() and "B" in row.to_html()
    col = ColStack([(para1, 50), (para2, 50)])
    assert "A" in col.to_text() and "B" in col.to_text()
    assert "A" in col.to_html() and "B" in col.to_html()
    spacer = Spacer(10)
    assert spacer.to_text() == ""
    assert "10" in spacer.to_html()
    boxcols = BoxCols([para1, para2])
    assert "A" in boxcols.to_html() and "B" in boxcols.to_html()


@pytest.mark.django_db
def test_timings_block():
    from uobtheatre.productions.test.factories import PerformanceFactory

    perf = PerformanceFactory()
    tb = TimingsBlock(perf)
    doors_str = perf.doors_open.astimezone(
        perf.venue.address.timezone
    ).strftime("%A, %d %B %Y at %H:%M (%Z)")
    start_str = perf.start.astimezone(perf.venue.address.timezone).strftime(
        "%A, %d %B %Y at %H:%M (%Z)"
    )
    text = tb.to_text()
    assert "Timings" in text
    assert doors_str in text
    assert start_str in text
    assert tb.latecomerDisclaimer in text
    html = tb.to_html()
    # The disclaimer may be HTML-escaped in the output, so check for both
    import html as html_module

    disclaimer = tb.latecomerDisclaimer
    assert (disclaimer in html) or (html_module.escape(disclaimer) in html)
    assert "Doors Open" in html
    assert doors_str in html
    assert start_str in html


@pytest.mark.django_db
def test_booking_block():
    from uobtheatre.bookings.test.factories import BookingFactory

    booking = BookingFactory()
    bb = BookingBlock(booking)
    # Check that the booking reference is present in both text and html
    text = bb.to_text()
    assert "Booking Reference" in text
    assert booking.reference in text
    assert bb.bookingInfo in text
    html = bb.to_html()
    assert booking.reference in html
    assert "View Tickets" in html
    assert bb.bookingInfo in html
    # Also check that the booking's web_tickets_path is present in the html
    assert booking.web_tickets_path in html


def test_accessibility_block():
    ab = AccessibilityBlock()
    text = ab.to_text()
    # The to_text output strips HTML tags, so check for the plain text version
    assert "Accessibility Information" in text
    assert "support@uobtheatre.com" in text
    # The to_html output should contain the mailto link
    html = ab.to_html()
    assert "Accessibility Information" in html
    assert "mailto:support@uobtheatre.com" in html


@pytest.mark.django_db
def test_mailcomposer_blank_and_textonly():
    para = Paragraph("Hello!")
    mail = MailComposer.blank([para])
    assert "Hello!" in mail.to_text()
    assert "Hello!" in mail.to_html()
    textonly = MailComposer.text_only(title="Title", message="Msg")
    assert "Title" in textonly.to_text() and "Msg" in textonly.to_text()


def test_mailcomposer_send(monkeypatch):
    class DummyMsg:
        def send(self):
            self.sent = True

    class DummyMailComposer(MailComposer):
        def get_email(self, subject, to_email):
            self.called = True
            return DummyMsg()

    mail = DummyMailComposer()
    mail.items.append(Paragraph("Test"))
    mail.send("Subject", "to@example.com")
    assert hasattr(mail, "called")


@pytest.mark.django_db
def test_collect_sub_items():
    para = Paragraph("A")
    btn = Button("/b", "B")
    row = RowStack([para, btn])
    all_items = ComposerItemInterface.collect_sub_items(row)
    assert para in all_items and btn in all_items and row in all_items


@pytest.mark.django_db
def test_sub_items_recursive():
    para = Paragraph("A")
    btn = Button("/b", "B")
    col = ColStack([(para, 50), (btn, 50)])
    row = RowStack([col])
    all_items = ComposerItemInterface.collect_sub_items(row)
    assert (
        para in all_items
        and btn in all_items
        and col in all_items
        and row in all_items
    )
