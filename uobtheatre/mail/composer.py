import abc
from datetime import datetime
from typing import List, Union

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.html import strip_tags


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


class Heading(ComposerItemInterface):
    """A heading (i.e. <hX>) composer item"""

    def __init__(self, text, size=1) -> None:
        super().__init__()
        self.text = text
        self.size = size

    def to_text(self):
        return self.text

    def to_html(self):
        return "<h%s>%s</h%s>" % (self.size, self.text, self.size)


class Line(ComposerItemInterface):
    """A line/paragraph composer item"""

    def __init__(self, text) -> None:
        super().__init__()
        self.text = text

    def to_text(self):
        return strip_tags(self.text)

    def to_html(self):
        return "<p>%s</p>" % self.text


class Image(ComposerItemInterface):
    """A full-width image composer item"""

    def __init__(self, url) -> None:
        super().__init__()
        self.url = url

    def to_text(self):
        return None

    def to_html(self):
        template = get_template("components/image.html")
        return template.render({"url": self.url})


class Action(ComposerItemInterface):
    """An action button composer item"""

    def __init__(self, url, text) -> None:
        super().__init__()
        self.url = url if not url[0] == "/" else get_site_base() + url
        self.text = text

    def to_text(self):
        return "%s (%s)" % (self.text, self.url)

    def to_html(self):
        template = get_template("components/button.html")

        return template.render({"url": self.url, "text": self.text})


class MailComposer:
    """Compose a mail notificaiton"""

    items: List[ComposerItemInterface] = []
    subcopy: List[Line] = []

    def line(self, text: str):
        """A line (paragraph) of text. May contain simple HTML, which will be stripped for plain text version"""
        self.items.append(Line(text))
        return self

    def action(self, url, text):
        """Create an action button"""
        action = Action(url, text)
        self.items.append(action)
        self.subcopy.append(
            Line(
                "Can't click the '%s' button? Copy the following into your browser: '<a href='%s'>%s</a>'"
                % (text, action.url, action.url)
            )
        )
        return self

    def heading(self, text):
        """Create a heading (title)"""
        self.items.append(Heading(text))
        return self

    def image(self, url):
        """Create a full-width image"""
        self.items.append(Image(url))
        return self

    def get_complete_items(self):
        """Get the email body items (including any signature/signoff)"""
        return self.items + [Line("Thanks,"), Line("The UOBTheatre Team")]

    def to_plain_text(self):
        """Generate the plain text version of the email"""
        return """{}""".format(
            "\n\n".join([item.to_text() for item in self.get_complete_items() if item.to_text()])
        )

    def to_html(self):
        """Generate the HTML version of the email"""
        content = """{}""".format(
            "\n".join([item.to_html() or "" for item in self.get_complete_items()])
        )
        subcopy = "\n".join((item.to_html() for item in self.subcopy))

        email = get_template("base_email.html").render(
            {
                "site_url": get_site_base(),
                "content": content,
                "subcopy": subcopy,
                "footer": "&copy; UOB Theatre %s" % datetime.now().year,
            }
        )
        return email

    def send(self, subject, to_email):
        """Send the email to the given email with the given subject"""
        msg = EmailMultiAlternatives(
            subject, self.to_plain_text(), settings.DEFAULT_FROM_EMAIL, [to_email]
        )
        msg.attach_alternative(self.to_html(), "text/html")
        msg.send()
