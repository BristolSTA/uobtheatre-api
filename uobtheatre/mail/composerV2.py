import abc
from datetime import datetime
from typing import List, Optional, Union

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.html import strip_tags
from html2text import html2text

from uobtheatre.mail.tasks import send_emails
from uobtheatre.users.models import User


def get_site_base():
    return "https://%s" % Site.objects.get_current().domain


class ComposerItemInterface(abc.ABC):
    """Abstract interface for a mail composer item"""

    def to_text(self) -> Union[str, None]:
        """Generate the plain text version of this item"""
        raise NotImplementedError()

    def to_html(self) -> str:
        """Generate the HTML version of this item"""
        raise NotImplementedError()


class ComposerItemsContainer(ComposerItemInterface, abc.ABC):
    """Abstract container of composer items"""

    def __init__(self) -> None:
        super().__init__()
        self.items: List[ComposerItemInterface] = []

    def heading(self, message: str):
        """A Heading composer item"""
        self.items.append(Heading(message))
        return self

    def paragraph(self, title: str, message: str):
        """A Paragraph composer item"""
        self.items.append(Paragraph(title, message))
        return self

    def button(self, href: str, text: str):
        """A Button composer item"""
        self.items.append(Button(href, text))
        return self

    def image(self, alt: str, title: str, href: str, src: str):
        """An Image composer item"""
        self.items.append(Image(alt, title, href, src))
        return self

    def box(self, bgUrl: str, bgCol: str, content: ComposerItemInterface):
        """A Box composer item, used for holding arbitrary content with
        a background of an image or solid colour"""
        self.items.append(Box(bgUrl, bgCol, content))
        return self

    def rowStack(self, rowStack: List[ComposerItemInterface]):
        """A RowStack composer item"""
        self.items.append(RowStack(rowStack))
        return self

    def colStack(self, colStack: List[(ComposerItemInterface, float)]):
        """A RowStack composer item"""
        """Takes in a list of items to put in a row,
        along with their associated widths in percentages"""
        self.items.append(ColStack(colStack))
        return self

    def spacer(self, width: int, height: float):
        """A Spacer composer item"""
        """The height should be an integer, in pixels.
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
    """A Paragraph composer item"""

    def __init__(self, title, message) -> None:
        super().__init__()
        self.title = title
        self.message = message

    def to_text(self):
        return strip_tags(self.title) + "\n" + strip_tags(self.message)

    def to_html(self):
        template = get_template("componentsV2/paragraph.html")

        return template.render({"title": self.title, "message": self.message})


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


class Box(ComposerItemInterface):
    """A Box composer item, used for holding arbitrary content with
    a background of an image or solid colour"""

    def __init__(self, bgUrl, bgCol, content) -> None:
        super().__init__()
        self.bgUrl = bgUrl
        self.bgCol = bgCol
        self.content = content

    def to_text(self):
        return self.content.to_text()

    def to_html(self):
        template = get_template("componentsV2/box.html")

        return template.render({"bgUrl": self.bgUrl, "bgCol": self.bgCol, "content": self.content.to_html()})


class Image(ComposerItemInterface):
    """An Image composer item"""

    def __init__(self, alt, title, href, src) -> None:
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


class RowStack(ComposerItemInterface):
    """An RowStack composer item"""

    def __init__(self, rowStack) -> None:
        super().__init__()
        self.rowStack = rowStack

    def to_text(self):
        return "\n".join([row.content.to_text() for row in self.rowStack])

    def to_html(self):
        template = get_template("componentsV2/rowStack.html")

        return template.render({"rowStack": self.rowStack})


class ColStack(ComposerItemInterface):
    """A ColStack composer item"""
    """Takes in a list of items to put in a row,
        along with their associated widths in percentages"""

    def __init__(self, colStack) -> None:
        super().__init__()
        self.colStack = colStack

    def to_text(self):
        return "\n".join([col.content.to_text() for (col, _) in self.colStack])

    def to_html(self):
        template = get_template("componentsV2/colStack.html")

        return template.render({"colStack": self.colStack})


class Spacer(ComposerItemInterface):
    """A Spacer composer item"""

    """The height should be an integer, in pixels.
    The width should be a number between 0 and 100,
    representing a percentage of the total width."""

    def __init__(self, width, height) -> None:
        super().__init__()
        self.width = width
        self.height = height

    def to_text(self):
        return ""

    def to_html(self):
        template = get_template("componentsV2/spacer.html")

        return template.render({"width": self.width, "height": self.height})


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

    def get_complete_items(self):
        """Get the email body items (including any signature/signoff)"""
        return self.items

    def to_plain_text(self):
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

        print("Email: ", email)

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
