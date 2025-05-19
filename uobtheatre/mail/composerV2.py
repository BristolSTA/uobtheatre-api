import abc

from datetime import datetime
from typing import List, Optional, Union

import codecs

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.html import strip_tags
from html2text import html2text

import qrcode
import qrcode.image.svg

from uobtheatre.mail.tasks import send_emails
from uobtheatre.users.models import User

# Icons have to be SVG paths
# https://fontawesome.com/search?q=code&o=r&ic=free
icons = {
    "clock": "M464 256A208 208 0 1 1 48 256a208 208 0 1 1 416 0zM0 256a256 256 0 1 0 512 0A256 256 0 1 0 0 256zM232 120l0 136c0 8 4 15.5 10.7 20l96 64c11 7.4 25.9 4.4 33.3-6.7s4.4-25.9-6.7-33.3L280 243.2 280 120c0-13.3-10.7-24-24-24s-24 10.7-24 24z",
    "search": "M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L330.7 376c-34.4 25.2-76.8 40-122.7 40C93.1 416 0 322.9 0 208S93.1 0 208 0S416 93.1 416 208zM208 352a144 144 0 1 0 0-288 144 144 0 1 0 0 288z",
    "door-open": "M320 32c0-9.9-4.5-19.2-12.3-25.2S289.8-1.4 280.2 1l-179.9 45C79 51.3 64 70.5 64 92.5L64 448l-32 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l64 0 192 0 32 0 0-32 0-448zM256 256c0 17.7-10.7 32-24 32s-24-14.3-24-32s10.7-32 24-32s24 14.3 24 32zm96-128l96 0 0 352c0 17.7 14.3 32 32 32l64 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-32 0 0-320c0-35.3-28.7-64-64-64l-96 0 0 64z",
    "play": "M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80L0 432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z",
    "barcode": "M0 80C0 53.5 21.5 32 48 32l96 0c26.5 0 48 21.5 48 48l0 96c0 26.5-21.5 48-48 48l-96 0c-26.5 0-48-21.5-48-48L0 80zM64 96l0 64 64 0 0-64L64 96zM0 336c0-26.5 21.5-48 48-48l96 0c26.5 0 48 21.5 48 48l0 96c0 26.5-21.5 48-48 48l-96 0c-26.5 0-48-21.5-48-48l0-96zm64 16l0 64 64 0 0-64-64 0zM304 32l96 0c26.5 0 48 21.5 48 48l0 96c0 26.5-21.5 48-48 48l-96 0c-26.5 0-48-21.5-48-48l0-96c0-26.5 21.5-48 48-48zm80 64l-64 0 0 64 64 0 0-64zM256 304c0-8.8 7.2-16 16-16l64 0c8.8 0 16 7.2 16 16s7.2 16 16 16l32 0c8.8 0 16-7.2 16-16s7.2-16 16-16s16 7.2 16 16l0 96c0 8.8-7.2 16-16 16l-64 0c-8.8 0-16-7.2-16-16s-7.2-16-16-16s-16 7.2-16 16l0 64c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-160zM368 480a16 16 0 1 1 0-32 16 16 0 1 1 0 32zm64 0a16 16 0 1 1 0-32 16 16 0 1 1 0 32z",
    "accessibility": "M192 96a48 48 0 1 0 0-96 48 48 0 1 0 0 96zM120.5 247.2c12.4-4.7 18.7-18.5 14-30.9s-18.5-18.7-30.9-14C43.1 225.1 0 283.5 0 352c0 88.4 71.6 160 160 160c61.2 0 114.3-34.3 141.2-84.7c6.2-11.7 1.8-26.2-9.9-32.5s-26.2-1.8-32.5 9.9C240 440 202.8 464 160 464C98.1 464 48 413.9 48 352c0-47.9 30.1-88.8 72.5-104.8zM259.8 176l-1.9-9.7c-4.5-22.3-24-38.3-46.8-38.3c-30.1 0-52.7 27.5-46.8 57l23.1 115.5c6 29.9 32.2 51.4 62.8 51.4l5.1 0c.4 0 .8 0 1.3 0l94.1 0c6.7 0 12.6 4.1 15 10.4L402 459.2c6 16.1 23.8 24.6 40.1 19.1l48-16c16.8-5.6 25.8-23.7 20.2-40.5s-23.7-25.8-40.5-20.2l-18.7 6.2-25.5-68c-11.7-31.2-41.6-51.9-74.9-51.9l-68.5 0-9.6-48 63.4 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-76.2 0z",
    "money": "M96 96l0 224c0 35.3 28.7 64 64 64l416 0c35.3 0 64-28.7 64-64l0-224c0-35.3-28.7-64-64-64L160 32c-35.3 0-64 28.7-64 64zm64 160c35.3 0 64 28.7 64 64l-64 0 0-64zM224 96c0 35.3-28.7 64-64 64l0-64 64 0zM576 256l0 64-64 0c0-35.3 28.7-64 64-64zM512 96l64 0 0 64c-35.3 0-64-28.7-64-64zM288 208a80 80 0 1 1 160 0 80 80 0 1 1 -160 0zM48 120c0-13.3-10.7-24-24-24S0 106.7 0 120L0 360c0 66.3 53.7 120 120 120l400 0c13.3 0 24-10.7 24-24s-10.7-24-24-24l-400 0c-39.8 0-72-32.2-72-72l0-240z",
    "card": "M64 32C28.7 32 0 60.7 0 96l0 32 576 0 0-32c0-35.3-28.7-64-64-64L64 32zM576 224L0 224 0 416c0 35.3 28.7 64 64 64l448 0c35.3 0 64-28.7 64-64l0-192zM112 352l64 0c8.8 0 16 7.2 16 16s-7.2 16-16 16l-64 0c-8.8 0-16-7.2-16-16s7.2-16 16-16zm112 16c0-8.8 7.2-16 16-16l128 0c8.8 0 16 7.2 16 16s-7.2 16-16 16l-128 0c-8.8 0-16-7.2-16-16z",
    "trolley": "M0 24C0 10.7 10.7 0 24 0L69.5 0c22 0 41.5 12.8 50.6 32l411 0c26.3 0 45.5 25 38.6 50.4l-41 152.3c-8.5 31.4-37 53.3-69.5 53.3l-288.5 0 5.4 28.5c2.2 11.3 12.1 19.5 23.6 19.5L488 336c13.3 0 24 10.7 24 24s-10.7 24-24 24l-288.3 0c-34.6 0-64.3-24.6-70.7-58.5L77.4 54.5c-.7-3.8-4-6.5-7.9-6.5L24 48C10.7 48 0 37.3 0 24zM128 464a48 48 0 1 1 96 0 48 48 0 1 1 -96 0zm336-48a48 48 0 1 1 0 96 48 48 0 1 1 0-96z",
    "ticket": "M64 64C28.7 64 0 92.7 0 128l0 64c0 8.8 7.4 15.7 15.7 18.6C34.5 217.1 48 235 48 256s-13.5 38.9-32.3 45.4C7.4 304.3 0 311.2 0 320l0 64c0 35.3 28.7 64 64 64l448 0c35.3 0 64-28.7 64-64l0-64c0-8.8-7.4-15.7-15.7-18.6C541.5 294.9 528 277 528 256s13.5-38.9 32.3-45.4c8.3-2.9 15.7-9.8 15.7-18.6l0-64c0-35.3-28.7-64-64-64L64 64zm64 112l0 160c0 8.8 7.2 16 16 16l288 0c8.8 0 16-7.2 16-16l0-160c0-8.8-7.2-16-16-16l-288 0c-8.8 0-16 7.2-16 16zM96 160c0-17.7 14.3-32 32-32l320 0c17.7 0 32 14.3 32 32l0 192c0 17.7-14.3 32-32 32l-320 0c-17.7 0-32-14.3-32-32l0-192z",
    "bookmark": "M336 0H48C21.5 0 0 21.5 0 48v464l192-112 192 112V48c0-26.5-21.5-48-48-48zm0 428.4l-144-84-144 84V54a6 6 0 0 1 6-6h276c3.3 0 6 2.7 6 6V428.4z"
}

def get_site_base():
    return "https://%s" % Site.objects.get_current().domain


class ComposerItemInterface(abc.ABC):
    """Abstract interface for a mail composer item"""

    def to_text(self) -> str:
        """Generate the plain text version of this item"""
        raise NotImplementedError()

    def to_html(self) -> str:
        """Generate the HTML version of this item"""
        raise NotImplementedError()

    def sub_items(self):
        """Return a list of all sub items that a composer item contains (e.g. a rowStack or colStack),
        as well as itself.
        Most items will return a list of just themselves here by default."""
        return [self]


class ComposerItemsContainer(ComposerItemInterface, abc.ABC):
    """Abstract container of composer items"""

    def __init__(self) -> None:
        super().__init__()
        self.items: List[ComposerItemInterface] = []

    def heading(self, message: str):
        """A Heading composer item"""
        self.items.append(Heading(message))
        return self

    def paragraph(self, title: str, message: str, titleIcon: str, messageIcon: str, html: bool):
        """A Paragraph composer item"""
        self.items.append(
            Paragraph(title, message, titleIcon, messageIcon, html))
        return self

    def button(self, href: str, text: str):
        """A Button composer item"""
        self.items.append(Button(href, text))
        return self

    def buttonHelpText(self, href: str, text: str):
        """A ButtonHelpText composer item"""
        self.items.append(ButtonHelpText(href, text))
        return self

    def image(self, src: str, alt="", title="", href=""):
        """An Image composer item"""
        self.items.append(Image(src, alt, title, href))
        return self

    def qr(self, content):
        """An QR composer item"""
        self.items.append(QR(content))
        return self

    def logo(self):
        """A UOB Theatre Logo item"""
        self.items.append(Logo())
        return self

    def footer(self):
        """A UOB Theatre Footer item"""
        self.items.append(Footer())
        return self

    def box(self, content: ComposerItemInterface, bgUrl="", bgCol="#D0D0D0"):
        """A Box composer item, used for holding arbitrary content with
        a background of an image or solid colour"""
        self.items.append(Box(bgUrl, bgCol, content))
        return self

    def rowStack(self, rowStack: List[ComposerItemInterface]):
        """A RowStack composer item"""
        self.items.append(RowStack(rowStack))
        return self

    def colStack(self, colStack: List[object]):
        """A ColStack composer item.
        Takes in a list of items to put in a row,
        along with their associated widths as a string, in %.
        i.e., really a list of type List[(ComposerItemInterface, float)]"""
        self.items.append(ColStack(colStack))
        return self

    def boxCols(self, content: List[ComposerItemInterface]):
        """This pre-makes a ColStack with an arbitrary number of even columns, using default
        boxes to hold the content. This is a quick and easy way to split content into columns."""
        self.items.append(BoxCols(content))
        return self

    def spacer(self, width=0, height=0):
        """A Spacer composer item.
        The height should be an integer, in pixels.
        The width should be a number between 0 and 100,
        representing a percentage of the total width."""
        self.items.append(Spacer(width, height))
        return self

    def append(self, item):
        self.items.append(item)
        return self

    def to_text(self) -> Union[str, None]:
        """Generate the plain text version of this item"""
        return """{}""".format(
            "\n\n".join(
                [item.to_text()
                 for item in self.items if item.to_text()]  # type: ignore
            )
        )

    def to_html(self) -> str:
        """Generate the HTML version of this item"""
        return """{}""".format("\n".join([item.to_html() or "" for item in self.items]))


class Heading(ComposerItemInterface):
    """A Heading composer item"""

    def __init__(self, message) -> None:
        super().__init__()
        self.message = message

    def to_text(self):
        return strip_tags(self.message)

    def to_html(self):
        template = get_template("componentsV2/heading.html")

        return template.render({"message": self.message})

class Paragraph(ComposerItemInterface):
    """A Paragraph composer item."""

    def __init__(self, title="", message="", titleIcon="", messageIcon="", html=False) -> None:
        """If html == True, then this string will parse the given HTML; be careful,
        as if used improperly, this may open up scripting attacks."""
        super().__init__()
        self.title = title
        self.message = message
        self.html = html
        self.titleIcon = icons[titleIcon] if titleIcon in icons.keys() else ""
        self.messageIcon = icons[messageIcon] if messageIcon in icons.keys(
        ) else ""

    def to_text(self):
        return strip_tags(self.title) + "\n" + strip_tags(self.message)

    def to_html(self):
        template = get_template("componentsV2/paragraph.html")

        return template.render({"title": self.title, "message": self.message, "messageIcon": self.messageIcon, "titleIcon": self.titleIcon, "html": self.html})


class Button(ComposerItemInterface):
    """A Button composer item"""

    def __init__(self, href, text) -> None:
        super().__init__()
        self.href = href
        self.text = text

    def to_text(self):
        return strip_tags(self.text) + "(" + strip_tags(self.href) + ")"

    def to_html(self):
        template = get_template("componentsV2/button.html")
        return template.render({"text": self.text, "href": self.href})


class ButtonHelpText(ComposerItemInterface):
    """A ButtonHelpText composer item"""

    def __init__(self, href, text) -> None:
        super().__init__()
        self.href = href
        self.text = text

    def to_text(self):
        return f"Can't click the \"{self.text}\" button above? Copy the following into your browser: {self.href}"

    def to_html(self):
        template = get_template("componentsV2/buttonHelp.html")
        return template.render({"text": self.text, "href": self.href})


class Box(ComposerItemInterface):
    """A Box composer item, used for holding arbitrary content with
    a background of an image or solid colour"""

    def __init__(self, content: ComposerItemInterface, bgUrl="", bgCol="#D0D0D0") -> None:
        super().__init__()
        self.bgUrl = bgUrl
        self.bgCol = bgCol
        self.content = content

    def to_text(self):
        return self.content.to_text()

    def to_html(self):
        template = get_template("componentsV2/box.html")

        return template.render({"bgUrl": self.bgUrl, "bgCol": self.bgCol, "content": self.content.to_html()})

    # Need to return the box's content as a subItem
    def sub_items(self):
        return [self] + self.content.sub_items()


class Image(ComposerItemInterface):
    """An Image composer item"""

    def __init__(self, src, alt="", title="", href="") -> None:
        super().__init__()
        self.href = href
        self.title = title
        self.alt = alt
        self.src = src

    def to_text(self):
        return strip_tags(self.alt)

    def to_html(self):
        template = get_template("componentsV2/image.html")

        return template.render({"alt": self.alt, "href": self.href, "src": self.src, "title": self.title})


class QR(ComposerItemInterface):
    """A QR composer item"""

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

        # Convert the content to a QR code
        qrFactory = qrcode.image.svg.SvgPathFillImage
        self.qr = qrcode.make(
            content, image_factory=qrFactory).to_string().decode("ascii")

    def to_text(self):
        return f"QR Code:\n{self.content}"

    def to_html(self):
        template = get_template("componentsV2/qrCode.html")

        return template.render({"qr": self.qr})


class TicketCodes(ComposerItemInterface):
    """A TicketCodes composer item"""

    def __init__(self, bookingRef: str, ticketIds: list[str]) -> None:
        super().__init__()
        self.bookingRef = bookingRef
        self.ticketIds = ticketIds
        self.ticketData = []
        self.plural = "" if len(self.ticketData) == 1 else "s"

        # Convert the tickets to data strings for the QR codes
        for ticketId in ticketIds:
            # Encode the ticket data to base64
            b64String = codecs.encode(
                f"[\"{bookingRef}\",\"{ticketId}\"]".encode(), "base64_codec").decode()[:-1]

            self.ticketData.append(b64String)

    def to_text(self):
        plaintext = f"{len(self.ticketData)} ticket QR code{self.plural}:"

        for ticketData in self.ticketData:
            plaintext += f"\n{ticketData}"

        return plaintext

    def to_html(self):
        # Maximum tickets per grid row, and as many grid rows as we need
        maxPerRow = 3

        qrContent = []
        row = 0

        # Create a grid of tickets as needed
        while row < len(self.ticketData):
            col = 0
            rowContent = []

            while row + col < len(self.ticketData):

                # Create the ticket box
                rowContent.append(RowStack(
                    [Paragraph(title=f"Ticket {row+col+1}"), QR(self.ticketData[row + col])]))
                col += 1

                # Limit the number of tickets per row
                if col == maxPerRow:
                    break

            # Add the columnStack to the content
            qrContent.append(BoxCols(rowContent))

            # Update the number of tickets added so far
            row += maxPerRow

        # Generate a pretty ticket element
        content = RowStack(
            [Paragraph(title=f"Your Ticket{self.plural}", titleIcon="ticket")]
            + qrContent)

        return content.to_html()

class Logo(ComposerItemInterface):
    """A UOB Theatre Logo item"""

    def to_text(self):
        return "Stage Technicians' Association | UOB Theatre"

    def to_html(self):
        template = get_template("componentsV2/logo.html")

        return template.render({"site_url": get_site_base()})


class Footer(ComposerItemInterface):
    """A UOB Theatre Footer item"""

    def to_text(self):
        return f"Copyright UOB Theatre {datetime.now().year}"

    def to_html(self):
        template = get_template("componentsV2/footer.html")

        return template.render({"year": datetime.now().year})

class RowStack(ComposerItemInterface):
    """A RowStack composer item"""

    def __init__(self, rowStack: List[ComposerItemInterface]) -> None:
        super().__init__()
        self.rowStack = rowStack

    def to_text(self):
        return "\n".join([row.to_text() for row in self.rowStack])

    def to_html(self):
        template = get_template("componentsV2/rowStack.html")

        return template.render({"rowStack": [row.to_html() for row in self.rowStack]})

    # Export and flatten the RowStack's sub items
    def sub_items(self):
        return [self] + [item for row in self.rowStack for item in row.sub_items()]

class ColStack(ComposerItemInterface):
    """A ColStack composer item.
    Takes in a list of items to put in a row,
        along with their associated widths as a float, in %."""

    def __init__(self, colStack: List[tuple[ComposerItemInterface, float]]) -> None:
        super().__init__()
        self.colStack = colStack

    def to_text(self):
        return "\n".join([col.to_text() for (col, _) in self.colStack if col.to_text()])

    def to_html(self):
        template = get_template("componentsV2/colStack.html")

        return template.render({"colStack": [(col.to_html(), width) for (col, width) in self.colStack]})

    # Export and flatten the RowStack's sub items
    def sub_items(self):
        return [self] + [item for (col, _) in self.colStack for item in col.sub_items()]


class Spacer(ComposerItemInterface):
    """A Spacer composer item.
    The height should be an integer, in pixels.
    The width should be a number between 0 and 100,
    representing a percentage of the total width."""

    def __init__(self, width=0, height=0) -> None:
        super().__init__()
        self.width = width
        self.height = height

    def to_text(self):
        return ""

    def to_html(self):
        template = get_template("componentsV2/spacer.html")

        return template.render({"width": self.width, "height": self.height})


class BoxCols(ColStack):

    """This pre-makes a ColStack with an arbitrary number of even columns, using default
    boxes to hold the content. This is a quick and easy way to split content into columns."""

    def __init__(self, content):

        colCount = len(content)
        spacerWidth = min(1, 5 - colCount)
        colWidth = (100 - (colCount + 1) * spacerWidth) / colCount

        cols = [(Spacer(), spacerWidth)]

        for i in range(colCount):
            cols.append((Box(content[i]), colWidth))
            cols.append((Spacer(), spacerWidth))

        super().__init__(cols)


class MailComposer(ComposerItemsContainer):
    """Compose a mail notificaiton"""

    def greeting(self, user: Optional[User] = None):
        """Add a greeting to the email"""
        self.heading(
            "Hi %s" % user.first_name.capitalize()
            if user and user.status.verified  # type: ignore
            else "Hello"
        )
        return self

    def blank(content: list[ComposerItemInterface]) -> ComposerItemInterface:
        """Create a blank email, with the content (a list of elements to go in a RowStack) within.
        This will also add a footer component with extra button details."""

        # Prepare the footer for the buttons
        buttons = []
        for item in [item for row in content for item in row.sub_items()]:
            if item.__class__ == Button:
                buttons.append(ButtonHelpText(item.href, item.text))

        mail = (MailComposer()
                .colStack([
                    (Spacer(), 10),
                    (RowStack([
                        Logo(),
                        Spacer(height=15),
                        Box(RowStack(content), bgCol="white"),
                        Spacer(height=15),
                        Footer(),
                        # If there are buttons, add that after the footer
                        Spacer(height=(15 if len(buttons) > 0 else 0)),
                        Box(RowStack(buttons), bgCol="rgba(0,0,0,0.2)"),
                    ]), 80),
                    (Spacer(), 10)
                ]))

        return mail

    def textOnly(title="", message="", html=False) -> ComposerItemInterface:
        """Create an email that is text only. Takes in just a title and message.
        If html == True, then this string will parse any given HTML; be careful,
        as if used improperly, this may open up scripting attacks."""
        return MailComposer.blank([Box(Paragraph(title, message, html), bgCol="white")])

    def get_complete_items(self):
        """Get the email body items (including any signature/signoff)"""
        return self.items

    def to_plain_text(self) -> str:
        """Generate the plain text version of the email"""
        return """{}""".format(
            "\n\n".join(
                [item.to_text()
                 for item in self.get_complete_items() if item.to_text()]
            )
        )

    def to_html(self):
        """Generate the HTML version of the email"""
        content = """{}""".format(
            "\n".join(
                [item.to_html() or "" for item in self.get_complete_items()])
        )

        email = get_template("new_base.html").render(
            {
                "content": content,
            }
        )

        return email

    def get_email(self, subject, to_email):
        msg = EmailMultiAlternatives(
            subject, self.to_plain_text(), settings.DEFAULT_FROM_EMAIL, [
                to_email]
        )
        msg.attach_alternative(self.to_html(), "text/html")
        return msg

    def send(self, subject, to_email):
        """Send the email to the given email with the given subject"""
        msg = self.get_email(subject, to_email)
        msg.send()

    def sub_items(self):
        return [subItem for child in self.items for subItem in child.sub_items()]


class MassMailComposer:
    """Send many emails"""

    def __init__(
        self,
        users: list[User],
        subject: str,
        mail_compose: MailComposer,
    ) -> None:
        """Initalise the mass mail"""
        self.subject = subject
        self.users = users
        self.mail_compose = mail_compose

    def send_async(self):
        """Send the mass mail"""
        if not self.users:
            return

        send_emails.delay(
            [user.email for user in self.users],
            self.subject,
            self.mail_compose.to_plain_text(),
            self.mail_compose.to_html(),
        )
