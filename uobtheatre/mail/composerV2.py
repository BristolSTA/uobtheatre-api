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

    def paragraph(self, title: str, message: str, titleIcon: str, messageIcon: str):
        """A Paragraph composer item"""
        self.items.append(Paragraph(title, message))
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
        self.titleIcon = titleIcon
        self.messageIcon = messageIcon

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
    """An QR composer item"""

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

        # Encode the content to base64
        b64String = codecs.encode(
            content.encode(), "base64_codec").decode()[:-1]

        # Then convert it to a QR code
        qrFactory = qrcode.image.svg.SvgPathFillImage
        self.qr = qrcode.make(
            b64String, image_factory=qrFactory).to_string().decode("ascii")

    def to_text(self):
        return f"QR Code:\n{self.content}"

    def to_html(self):
        template = get_template("componentsV2/qrCode.html")

        return template.render({"qr": self.qr})

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
        return "\n".join([col.to_text() for [col, _] in self.colStack])

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
