import abc
import codecs
from datetime import datetime
from typing import List, Optional, Sequence, Union, overload
from urllib.parse import quote_plus

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.html import strip_tags
from html2text import html2text

from uobtheatre.mail.tasks import send_emails
from uobtheatre.users.models import User

# Icons have to be SVG paths
# https://fontawesome.com/search?q=code&o=r&ic=free
icons = {
    "clock": {
        "size": "0 0 512 512",
        "path": "M464 256a208 208 0 1 1 -416 0 208 208 0 1 1 416 0zM0 256a256 256 0 1 0 512 0 256 256 0 1 0 -512 0zM232 120l0 136c0 8 4 15.5 10.7 20l96 64c11 7.4 25.9 4.4 33.3-6.7s4.4-25.9-6.7-33.3L280 243.2 280 120c0-13.3-10.7-24-24-24s-24 10.7-24 24z",
    },
    "search": {
        "size": "0 0 512 512",
        "path": "M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L330.7 376C296.3 401.1 253.9 416 208 416 93.1 416 0 322.9 0 208S93.1 0 208 0 416 93.1 416 208zM208 352a144 144 0 1 0 0-288 144 144 0 1 0 0 288z",
    },
    "door-open": {
        "size": "0 0 448 512",
        "path": "M288 64l64 0 0 416c0 17.7 14.3 32 32 32l32 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l0-384c0-35.3-28.7-64-64-64l-96 0 0 0-160 0C60.7 0 32 28.7 32 64l0 384c-17.7 0-32 14.3-32 32s14.3 32 32 32l224 0c17.7 0 32-14.3 32-32l0-416zM160 256a32 32 0 1 1 64 0 32 32 0 1 1 -64 0z",
    },
    "play": {
        "size": "0 0 448 512",
        "path": "M91.2 36.9c-12.4-6.8-27.4-6.5-39.6 .7S32 57.9 32 72l0 368c0 14.1 7.5 27.2 19.6 34.4s27.2 7.5 39.6 .7l336-184c12.8-7 20.8-20.5 20.8-35.1s-8-28.1-20.8-35.1l-336-184z",
    },
    "barcode": {
        "size": "0 0 448 512",
        "path": "M32 32C14.3 32 0 46.3 0 64L0 448c0 17.7 14.3 32 32 32s32-14.3 32-32L64 64c0-17.7-14.3-32-32-32zm88 0c-13.3 0-24 10.7-24 24l0 400c0 13.3 10.7 24 24 24s24-10.7 24-24l0-400c0-13.3-10.7-24-24-24zm72 32l0 384c0 17.7 14.3 32 32 32s32-14.3 32-32l0-384c0-17.7-14.3-32-32-32s-32 14.3-32 32zm208-8l0 400c0 13.3 10.7 24 24 24s24-10.7 24-24l0-400c0-13.3-10.7-24-24-24s-24 10.7-24 24zm-96 0l0 400c0 13.3 10.7 24 24 24s24-10.7 24-24l0-400c0-13.3-10.7-24-24-24s-24 10.7-24 24z",
    },
    "accessibility": {
        "size": "0 0 576 512",
        "path": "M268.9 53.2L152.3 182.8c-4.6 5.1-4.4 13 .5 17.9 30.5 30.5 80 30.5 110.5 0l31.8-31.8c4.2-4.2 9.5-6.5 14.9-6.9 6.8-.6 13.8 1.7 19 6.9L505.6 344 576 288 576 0 464 64 440.2 48.1C424.4 37.6 405.9 32 386.9 32l-70.4 0c-1.1 0-2.3 0-3.4 .1-16.9 .9-32.8 8.5-44.2 21.1zM116.6 150.7L223.4 32 183.8 32c-25.5 0-49.9 10.1-67.9 28.1L0 192 0 544 144 408 156.4 418.3c23 19.2 52 29.7 81.9 29.7l15.7 0-7-7c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l41 41 9 0c19.1 0 37.8-4.3 54.8-12.3L359 409c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l32 32 17.5-17.5c8.9-8.9 11.5-21.8 7.6-33.1l-137.9-136.8-14.9 14.9c-49.3 49.3-129.1 49.3-178.4 0-23-23-23.9-59.9-2.2-84z",
    },
    "money": {
        "size": "0 0 576 512",
        "path": "M160 32c-35.3 0-64 28.7-64 64l0 224c0 35.3 28.7 64 64 64l352 0c35.3 0 64-28.7 64-64l0-224c0-35.3-28.7-64-64-64L160 32zm176 96a80 80 0 1 1 0 160 80 80 0 1 1 0-160zM160 152l0-48c0-4.4 3.6-8 8-8l48 0c4.4 0 8.1 3.6 7.5 8-3.6 29-26.6 51.9-55.5 55.5-4.4 .5-8-3.1-8-7.5zm0 112c0-4.4 3.6-8.1 8-7.5 29 3.6 51.9 26.6 55.5 55.5 .5 4.4-3.1 8-7.5 8l-48 0c-4.4 0-8-3.6-8-8l0-48zM504 159.5c-29-3.6-51.9-26.6-55.5-55.5-.5-4.4 3.1-8 7.5-8l48 0c4.4 0 8 3.6 8 8l0 48c0 4.4-3.6 8.1-8 7.5zM512 264l0 48c0 4.4-3.6 8-8 8l-48 0c-4.4 0-8.1-3.6-7.5-8 3.6-29 26.6-51.9 55.5-55.5 4.4-.5 8 3.1 8 7.5zM48 152c0-13.3-10.7-24-24-24S0 138.7 0 152L0 416c0 35.3 28.7 64 64 64l392 0c13.3 0 24-10.7 24-24s-10.7-24-24-24L64 432c-8.8 0-16-7.2-16-16l0-264z",
    },
    "card": {
        "size": "0 0 512 512",
        "path": "M0 128l0 32 512 0 0-32c0-35.3-28.7-64-64-64L64 64C28.7 64 0 92.7 0 128zm0 80L0 384c0 35.3 28.7 64 64 64l384 0c35.3 0 64-28.7 64-64l0-176-512 0zM64 360c0-13.3 10.7-24 24-24l48 0c13.3 0 24 10.7 24 24s-10.7 24-24 24l-48 0c-13.3 0-24-10.7-24-24zm144 0c0-13.3 10.7-24 24-24l64 0c13.3 0 24 10.7 24 24s-10.7 24-24 24l-64 0c-13.3 0-24-10.7-24-24z",
    },
    "trolley": {
        "size": "0 0 640 512",
        "path": "M24-16C10.7-16 0-5.3 0 8S10.7 32 24 32l45.3 0c3.9 0 7.2 2.8 7.9 6.6l52.1 286.3c6.2 34.2 36 59.1 70.8 59.1L456 384c13.3 0 24-10.7 24-24s-10.7-24-24-24l-255.9 0c-11.6 0-21.5-8.3-23.6-19.7l-5.1-28.3 303.6 0c30.8 0 57.2-21.9 62.9-52.2L568.9 69.9C572.6 50.2 557.5 32 537.4 32l-412.7 0-.4-2c-4.8-26.6-28-46-55.1-46L24-16zM208 512a48 48 0 1 0 0-96 48 48 0 1 0 0 96zm224 0a48 48 0 1 0 0-96 48 48 0 1 0 0 96z",
    },
    "ticket": {
        "size": "0 0 576 512",
        "path": "M64 64C28.7 64 0 92.7 0 128l0 64C0 200.8 7.4 207.7 15.7 210.6 34.5 217.1 48 235 48 256s-13.5 38.9-32.3 45.4C7.4 304.3 0 311.2 0 320l0 64c0 35.3 28.7 64 64 64l448 0c35.3 0 64-28.7 64-64l0-64c0-8.8-7.4-15.7-15.7-18.6-18.8-6.5-32.3-24.4-32.3-45.4s13.5-38.9 32.3-45.4c8.3-2.9 15.7-9.8 15.7-18.6l0-64c0-35.3-28.7-64-64-64L64 64zM416 336l0-160-256 0 0 160 256 0zM112 160c0-17.7 14.3-32 32-32l288 0c17.7 0 32 14.3 32 32l0 192c0 17.7-14.3 32-32 32l-288 0c-17.7 0-32-14.3-32-32l0-192z",
    },
    "bookmark": {
        "size": "0 0 384 512",
        "path": "M0 64C0 28.7 28.7 0 64 0L320 0c35.3 0 64 28.7 64 64l0 417.1c0 25.6-28.5 40.8-49.8 26.6L192 412.8 49.8 507.7C28.5 521.9 0 506.6 0 481.1L0 64zM64 48c-8.8 0-16 7.2-16 16l0 387.2 117.4-78.2c16.1-10.7 37.1-10.7 53.2 0L336 451.2 336 64c0-8.8-7.2-16-16-16L64 48z",
    },
    "building": {
        "size": "0 0 384 576",
        "path": "M64 0C28.7 0 0 28.7 0 64L0 448c0 35.3 28.7 64 64 64l256 0c35.3 0 64-28.7 64-64l0-384c0-35.3-28.7-64-64-64L64 0zM176 352l32 0c17.7 0 32 14.3 32 32l0 80-96 0 0-80c0-17.7 14.3-32 32-32zM96 112c0-8.8 7.2-16 16-16l32 0c8.8 0 16 7.2 16 16l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32zM240 96l32 0c8.8 0 16 7.2 16 16l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16zM96 240c0-8.8 7.2-16 16-16l32 0c8.8 0 16 7.2 16 16l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32zm144-16l32 0c8.8 0 16 7.2 16 16l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16z",
    },
    "city": {
        "size": "0 0 576 512",
        "path": "M320 0c-35.3 0-64 28.7-64 64l0 32-48 0 0-72c0-13.3-10.7-24-24-24s-24 10.7-24 24l0 72-64 0 0-72C96 10.7 85.3 0 72 0S48 10.7 48 24l0 74c-27.6 7.1-48 32.2-48 62L0 448c0 35.3 28.7 64 64 64l448 0c35.3 0 64-28.7 64-64l0-192c0-35.3-28.7-64-64-64l-64 0 0-128c0-35.3-28.7-64-64-64L320 0zm64 112l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16l32 0c8.8 0 16 7.2 16 16zm-16 80c8.8 0 16 7.2 16 16l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16l32 0zm16 112l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16l32 0c8.8 0 16 7.2 16 16zm112-16c8.8 0 16 7.2 16 16l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16l32 0zM256 304l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16l32 0c8.8 0 16 7.2 16 16zM240 192c8.8 0 16 7.2 16 16l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16l32 0zM128 304l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16l32 0c8.8 0 16 7.2 16 16zM112 192c8.8 0 16 7.2 16 16l0 32c0 8.8-7.2 16-16 16l-32 0c-8.8 0-16-7.2-16-16l0-32c0-8.8 7.2-16 16-16l32 0z",
    },
    "compass": {
        "size": "0 0 512 512",
        "path": "M256 512a256 256 0 1 0 0-512 256 256 0 1 0 0 512zm50.7-186.9L162.4 380.6c-19.4 7.5-38.5-11.6-31-31l55.5-144.3c3.3-8.5 9.9-15.1 18.4-18.4l144.3-55.5c19.4-7.5 38.5 11.6 31 31L325.1 306.7c-3.2 8.5-9.9 15.1-18.4 18.4zM288 256a32 32 0 1 0 -64 0 32 32 0 1 0 64 0z",
    },
    "square-check": {
        "size": "0 0 448 512",
        "path": "M384 32c35.3 0 64 28.7 64 64l0 320c0 35.3-28.7 64-64 64L64 480c-35.3 0-64-28.7-64-64L0 96C0 60.7 28.7 32 64 32l320 0zM342 145.7c-10.7-7.8-25.7-5.4-33.5 5.3L189.1 315.2 137 263.1c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l72 72c5 5 11.9 7.5 18.8 7s13.4-4.1 17.5-9.8L347.3 179.2c7.8-10.7 5.4-25.7-5.3-33.5z",
    },
    "rocket": {
        "size": "0 0 512 512",
        "path": "M128 320L24.5 320c-24.9 0-40.2-27.1-27.4-48.5L50 183.3C58.7 168.8 74.3 160 91.2 160l95 0c76.1-128.9 189.6-135.4 265.5-124.3 12.8 1.9 22.8 11.9 24.6 24.6 11.1 75.9 4.6 189.4-124.3 265.5l0 95c0 16.9-8.8 32.5-23.3 41.2l-88.2 52.9c-21.3 12.8-48.5-2.6-48.5-27.4L192 384c0-35.3-28.7-64-64-64l-.1 0zM400 160a48 48 0 1 0 -96 0 48 48 0 1 0 96 0z",
    },
    "alert-triangle": {
        "size": "0 0 512 512",
        "path": "M256 0c14.7 0 28.2 8.1 35.2 21l216 400c6.7 12.4 6.4 27.4-.8 39.5S486.1 480 472 480L40 480c-14.1 0-27.2-7.4-34.4-19.5s-7.5-27.1-.8-39.5l216-400c7-12.9 20.5-21 35.2-21zm0 352a32 32 0 1 0 0 64 32 32 0 1 0 0-64zm0-192c-18.2 0-32.7 15.5-31.4 33.7l7.4 104c.9 12.5 11.4 22.3 23.9 22.3 12.6 0 23-9.7 23.9-22.3l7.4-104c1.3-18.2-13.1-33.7-31.4-33.7z",
    },
    "comments": {
        "size": "0 0 576 512",
        "path": "M384 144c0 97.2-86 176-192 176-26.7 0-52.1-5-75.2-14L35.2 349.2c-9.3 4.9-20.7 3.2-28.2-4.2s-9.2-18.9-4.2-28.2l35.6-67.2C14.3 220.2 0 183.6 0 144 0 46.8 86-32 192-32S384 46.8 384 144zm0 368c-94.1 0-172.4-62.1-188.8-144 120-1.5 224.3-86.9 235.8-202.7 83.3 19.2 145 88.3 145 170.7 0 39.6-14.3 76.2-38.4 105.6l35.6 67.2c4.9 9.3 3.2 20.7-4.2 28.2s-18.9 9.2-28.2 4.2L459.2 498c-23.1 9-48.5 14-75.2 14z",
    },
    "key": {
        "size": "0 0 512 512",
        "path": "M336 352c97.2 0 176-78.8 176-176S433.2 0 336 0 160 78.8 160 176c0 18.7 2.9 36.8 8.3 53.7L7 391c-4.5 4.5-7 10.6-7 17l0 80c0 13.3 10.7 24 24 24l80 0c13.3 0 24-10.7 24-24l0-40 40 0c13.3 0 24-10.7 24-24l0-40 40 0c6.4 0 12.5-2.5 17-7l33.3-33.3c16.9 5.4 35 8.3 53.7 8.3zM376 96a40 40 0 1 1 0 80 40 40 0 1 1 0-80z",
    },
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

    def sub_items(self) -> list["ComposerItemInterface"]:
        """
        Return a list of all sub items that a composer item contains (e.g. a rowStack or colStack), as well as itself.
        Most items will return a list of just themselves here by default.
        """
        return [self]

    @staticmethod
    def collect_sub_items(
        item: "ComposerItemInterface",
    ) -> list["ComposerItemInterface"]:
        """
        Recursively collect all sub-items from a composer item tree.
        Returns a flat list of all items (including the root).
        """
        items: list["ComposerItemInterface"] = [item]
        if hasattr(item, "sub_items"):
            for sub in item.sub_items():
                if sub is not item:
                    items.extend(ComposerItemInterface.collect_sub_items(sub))
        return items


class ComposerItemsContainer(ComposerItemInterface, abc.ABC):
    """Abstract container of composer items"""

    def __init__(self) -> None:
        super().__init__()
        self.items: List[ComposerItemInterface] = []

    def paragraph(self, message: str):
        """A paragraph composer item"""
        self.items.append(Paragraph(message))
        return self

    def heading(
        self,
        title: str,
        message: str,
        title_icon: str,
        message_icon: str,
        html: bool,
    ):  # pylint: disable=too-many-arguments, too-many-positional-arguments
        """A heading composer item"""
        self.items.append(
            Heading(
                title=title,
                message=message,
                title_icon=title_icon,
                message_icon=message_icon,
                html_safe=html,
            )
        )
        return self

    def greeting(self, user: Optional[User] = None):
        """A greeting composer item"""
        self.items.append(Greeting(user))
        return self

    def closer(self):
        """A closer composer item"""
        self.items.append(Closer())
        return self

    def button(self, href: str, text: str):
        """A Button composer item"""
        self.items.append(Button(href, text))
        return self

    def button_help_text(self, href: str, text: str):
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

    def box(
        self,
        content: ComposerItemInterface,
        bg_url: str = "",
        bg_col: str = "#D0D0D0",
        mb: bool = True,
    ):
        """A Box composer item, used for holding arbitrary content with
        a background of an image or solid colour"""
        # Ensure argument order and names are correct for Box
        self.items.append(
            Box(content=content, bg_url=bg_url, bg_col=bg_col, mb=mb)
        )
        return self

    def row_stack(self, row_stack: Sequence[ComposerItemInterface]):
        """A RowStack composer item"""
        self.items.append(RowStack(list(row_stack)))
        return self

    def col_stack(
        self, col_stack: Sequence[tuple[ComposerItemInterface, float]]
    ):
        """A ColStack composer item.
        Takes in a list of items to put in a row,
        along with their associated widths as a string, in %.
        i.e., really a list of type List[(ComposerItemInterface, float)]"""
        self.items.append(ColStack(list(col_stack)))
        return self

    def box_cols(self, content: List[ComposerItemInterface]):
        """This pre-makes a ColStack with an arbitrary number of even columns, using default
        boxes to hold the content. This is a quick and easy way to split content into columns.
        """
        self.items.append(BoxCols(content))
        return self

    def spacer(self, height=0):
        """A Spacer composer item.
        The height should be an integer, in pixels."""
        self.items.append(Spacer(height))
        return self

    def timings_block(self, performance):
        """A TimingsBlock composer item.
        A compound item that contains the timings of a performance, along with a latecomer disclamer.
        """
        self.items.append(TimingsBlock(performance))
        return self

    def booking_block(self, booking):
        """A BookingBlock composer item.
        A compound item that contains the details of a booking, such as the reference, and buttons to view tickets and the booking.
        """
        self.items.append(BookingBlock(booking))
        return self

    def venue_accessibility_block(self, venue):
        """VenueAccessibilityBlock composer item.
        A compound item that contains information about venue accessibility."""
        self.items.append(VenueAccessibilityBlock(venue))
        return self

    def venue_block(self, venue):
        """A VenueBlock composer item.
        A compound item that contains information about a venue."""
        self.items.append(VenueBlock(venue))
        return self

    def booking_accessibility_block(self, booking):
        """A BookingAccessibilityBlock composer item.
        A compound item that contains information about booking accessibility.
        """
        self.items.append(BookingAccessibilityBlock(booking))
        return self

    def payment_block(self, payment):
        """A PaymentBlock composer item.
        A compound item that contains information about a payment, such as the amount, date, and method.
        """
        self.items.append(PaymentBlock(payment))
        return self

    def append(self, item):
        self.items.append(item)
        return self

    def to_text(self) -> str:
        """Generate the plain text version of this item"""
        return """{}""".format(
            "\n\n".join(
                [
                    item.to_text() for item in self.items if item.to_text()
                ]  # type: ignore
            )
        )

    def to_html(self) -> str:
        """Generate the HTML version of this item"""
        return """{}""".format(
            "\n".join([item.to_html() or "" for item in self.items])
        )


class Greeting(ComposerItemInterface):
    """
    A Greeting composer item

    Args:
        user (User, optional): The user to greet. If None, a generic greeting is used.
    """

    def __init__(self, user: Optional[User] = None) -> None:
        super().__init__()
        self.user = user
        opener_name = (
            self.user.first_name.capitalize()
            if self.user and self.user.first_name
            else None
        )
        self.opener = f"Hi {opener_name}," if opener_name else "Hello,"

    def to_text(self):
        return strip_tags(self.opener)

    def to_html(self):
        template = get_template("componentsV2/paragraph.html")
        return template.render({"message": self.opener})


class Closer(ComposerItemInterface):
    """
    A Closer composer item

    """

    def __init__(self) -> None:
        super().__init__()

    def to_text(self):
        return "Regards,\nThe UOB Theatre Team"

    def to_html(self):
        return Paragraph(
            message="Regards,<br>The UOB Theatre Team", html_safe=True
        ).to_html()


class Paragraph(ComposerItemInterface):
    """A Heading composer item"""

    def __init__(
        self, message: str = "", *, title: str = "", html_safe: bool = False
    ) -> None:
        super().__init__()
        self.message = message or title
        self.html_safe = html_safe

    def to_text(self):
        return strip_tags(self.message)

    def to_html(self):
        template = get_template("componentsV2/paragraph.html")

        return template.render(
            {"message": self.message, "htmlSafe": self.html_safe}
        )


class HTMLBlock(ComposerItemInterface):
    """A raw HTML block composer item"""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.html = html

    def to_text(self):
        return strip_tags(self.html)

    def to_html(self):
        return self.html


class Heading(ComposerItemInterface):
    """
    A Heading composer item.

    Args:
        title (str): The title of the heading
        subtitle (str): The subtitle of the heading
        subsubtitle (str): The subsubtitle of the heading
        message (str): The message displayed without padding below the heading
        message (str): The message displayed without padding below the heading
    title_icon (str): The icon to use for the title, from the icons dict
    message_icon (str): The icon to use for the message, from the icons dict
    html_safe (bool): Whether to parse the message as HTML or not (default: False)
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        title="",
        subtitle="",
        subsubtitle="",
        message="",
        title_icon="",
        message_icon="",
        html_safe=False,
    ) -> None:
        """If html_safe == True, then this string will parse the given HTML; be careful,
        as if used improperly, this may open up scripting attacks."""
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.subsubtitle = subsubtitle
        self.message = message
        self.html_safe = html_safe
        self.title_icon = icons[title_icon] if title_icon in icons else ""
        self.message_icon = (
            icons[message_icon] if message_icon in icons else ""
        )

    def to_text(self):
        text = ""
        if self.title:
            text += strip_tags(self.title) + "\n"
        if self.subtitle:
            text += strip_tags(self.subtitle) + "\n"
        if self.subsubtitle:
            text += strip_tags(self.subsubtitle) + "\n"
        if self.message:
            text += strip_tags(self.message) + "\n"
        return text.rstrip("\n")

    def to_html(self):
        template = get_template("componentsV2/heading.html")

        return template.render(
            {
                "title": self.title,
                "subtitle": self.subtitle,
                "subsubtitle": self.subsubtitle,
                "message": self.message,
                # Keep template keys camelCase for compatibility
                "messageIcon": self.message_icon,
                "titleIcon": self.title_icon,
                "htmlSafe": self.html_safe,
            }
        )


class ListItem(ComposerItemInterface):
    """
    A ListItem composer item

    Args:
        title (str): The title of the list item
        message (str): The message of the list item
        title_icon (str): The icon to use for the title, from the icons dict
        message_icon (str): The icon to use for the message, from the icons dict
        inline (bool): Whether to display the title and message on the same line or not (default: False)
        html_safe (bool): Whether to parse the message as HTML or not (default: False)
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        title="",
        message="",
        title_icon="",
        message_icon="",
        inline=False,
        html_safe=False,
    ) -> None:
        super().__init__()
        self.title = title
        self.message = message
        self.title_icon = icons[title_icon] if title_icon in icons else ""
        self.message_icon = (
            icons[message_icon] if message_icon in icons else ""
        )
        self.inline = inline
        self.html_safe = html_safe

    def to_text(self):
        return strip_tags(self.title) + ": " + strip_tags(self.message)

    def to_html(self):
        template = get_template("componentsV2/listItem.html")

        return template.render(
            {
                "title": self.title,
                "message": self.message,
                "messageIcon": self.message_icon,
                "titleIcon": self.title_icon,
                "inline": self.inline,
                "htmlSafe": self.html_safe,
            }
        )


class Button(ComposerItemInterface):
    """A Button composer item"""

    def __init__(self, href, text) -> None:
        super().__init__()
        self.href = href if not href[0] == "/" else get_site_base() + href
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
        return f'Can\'t click the "{self.text}" button above? Copy the following into your browser: {self.href}'

    def to_html(self):
        template = get_template("componentsV2/buttonHelp.html")
        return template.render({"text": self.text, "href": self.href})


class Box(ComposerItemInterface):
    """A Box composer item, used for holding arbitrary content with
    a background of an image or solid colour

    Args:
        content (ComposerItemInterface): The content to put inside the box
        bg_url (str): The URL of the background image (default: "")
        bg_col (str): The background color (default: "#D0D0D0")
        mb (bool): Whether to add a margin-bottom class (default: True)
    """

    def __init__(
        self,
        content: ComposerItemInterface,
        bg_url: str = "",
        bg_col: str = "#D0D0D0",
        mb: bool = True,
        **kwargs: object,
    ) -> None:
        super().__init__()
        # Support legacy/camelCase kwargs from visualisations: bgCol, mb
        if isinstance(kwargs.get("bgCol"), str):
            bg_col = kwargs["bgCol"]  # type: ignore[assignment]
        if isinstance(kwargs.get("bgUrl"), str):
            bg_url = kwargs["bgUrl"]  # type: ignore[assignment]
        if isinstance(kwargs.get("mb"), bool):
            mb = kwargs["mb"]  # type: ignore[assignment]
        self.bg_url = bg_url
        self.bg_col = bg_col
        self.content = content
        self.mb = mb

    def to_text(self):
        return self.content.to_text()

    def to_html(self):
        template = get_template("componentsV2/box.html")

        return template.render(
            {
                "mb": self.mb,
                # Keep template keys camelCase for compatibility
                "bgUrl": self.bg_url,
                "bgCol": self.bg_col,
                "content": self.content.to_html(),
            }
        )

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

        return template.render(
            {
                "alt": self.alt,
                "href": self.href,
                "src": self.src,
                "title": self.title,
            }
        )


class QR(ComposerItemInterface):
    """A QR composer item"""

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

        # Convert the content to a QR code
        qrFactory = qrcode.image.svg.SvgPathFillImage
        self.qr = (
            qrcode.make(content, image_factory=qrFactory, box_size=16)
            .to_string()
            .decode("ascii")
        )

    def to_text(self):
        return f"QR Code:\n{self.content}"

    def to_html(self):
        template = get_template("componentsV2/qrCode.html")

        return template.render({"qr": self.qr})


class TicketCodes(ComposerItemInterface):
    """A TicketCodes composer item"""

    def __init__(self, booking_ref: str, ticket_ids: list[str]) -> None:
        super().__init__()
        self.booking_ref = booking_ref
        self.ticket_ids = ticket_ids
        self.ticket_data: list[str] = []
        self.plural = "" if len(self.ticket_ids) == 1 else "s"

        # Convert the tickets to data strings for the QR codes
        for ticket_id in ticket_ids:
            # Encode the ticket data to base64
            b64_string = codecs.encode(
                f'["{booking_ref}","{ticket_id}"]'.encode(), "base64_codec"
            ).decode()[:-1]

            self.ticket_data.append(b64_string)

    def to_text(self):
        plaintext = f"{len(self.ticket_data)} ticket QR code{self.plural}:"

        for ticket_data in self.ticket_data:
            plaintext += f"\n{ticket_data}"

        return plaintext

    def to_html(self):
        # Maximum tickets per grid row, and as many grid rows as we need
        max_per_row = 2

        qr_content: list[ComposerItemInterface] = []
        row = 0

        # Create a grid of tickets as needed
        while row < len(self.ticket_data):
            col = 0
            row_content = []

            while row + col < len(self.ticket_data):

                # Create the ticket box
                row_content.append(
                    RowStack(
                        [
                            Heading(subsubtitle=f"Ticket {row+col+1}"),
                            QR(self.ticket_data[row + col]),
                        ]
                    )
                )
                col += 1

                # Limit the number of tickets per row
                if col == max_per_row:
                    break

            # Add the columnStack to the content
            qr_content.append(BoxCols(row_content))

            # Update the number of tickets added so far
            row += max_per_row

        # Generate a pretty ticket element
        content = RowStack(
            [
                Heading(
                    subtitle=f"Your Ticket{self.plural}", title_icon="ticket"
                )
            ]
            + qr_content
        )

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
    """
    A RowStack composer item. Contains a list of child composer items.
    """

    def __init__(self, row_stack: Sequence[ComposerItemInterface]) -> None:
        super().__init__()
        # Accept any sequence and normalize to list for internal storage
        self.row_stack: list[ComposerItemInterface] = list(row_stack)

    def _stack_items(self) -> list["ComposerItemInterface"]:
        return self.row_stack

    def to_text(self) -> str:
        return "\n".join([row.to_text() for row in self._stack_items()])

    def to_html(self) -> str:
        template = get_template("componentsV2/rowStack.html")
        return template.render(
            {"rowStack": [row.to_html() for row in self._stack_items()]}
        )

    def sub_items(self) -> list["ComposerItemInterface"]:
        subitems: list[ComposerItemInterface] = [self]
        for row in self._stack_items():
            if hasattr(row, "sub_items"):
                subitems.extend(row.sub_items())
            else:
                subitems.append(row)
        return subitems


class ColStack(ComposerItemInterface):
    """
    A ColStack composer item. Contains a list of (item, width) tuples.
    """

    def __init__(
        self, col_stack: Sequence[tuple[ComposerItemInterface, float]]
    ) -> None:
        super().__init__()
        # Accept any sequence and normalize to list for internal storage
        self.col_stack: list[tuple[ComposerItemInterface, float]] = list(
            col_stack
        )

    def _stack_items(self) -> list["ComposerItemInterface"]:
        return [col for (col, _) in self.col_stack]

    def to_text(self) -> str:
        return "\n".join(
            [col.to_text() for col in self._stack_items() if col.to_text()]
        )

    def to_html(self) -> str:
        template = get_template("componentsV2/colStack.html")
        return template.render(
            {
                "colStack": [
                    (col.to_html(), width) for (col, width) in self.col_stack
                ]
            }
        )

    def sub_items(self) -> list["ComposerItemInterface"]:
        subitems: list[ComposerItemInterface] = [self]
        for col in self._stack_items():
            if hasattr(col, "sub_items"):
                subitems.extend(col.sub_items())
            else:
                subitems.append(col)
        return subitems


class Spacer(ComposerItemInterface):
    """A Spacer composer item.
    The height should be an integer, in pixels."""

    def __init__(self, height=0) -> None:
        super().__init__()
        self.height = height

    def to_text(self):
        return ""

    def to_html(self):
        template = get_template("componentsV2/spacer.html")

        return template.render({"height": self.height})


class BoxCols(ColStack):
    """This pre-makes a ColStack with an arbitrary number of even columns, using default
    boxes to hold the content. This is a quick and easy way to split content into columns.
    """

    def __init__(self, content: Sequence[ComposerItemInterface]):
        col_width = 100 / len(content)
        cols: list[tuple[ComposerItemInterface, float]] = []
        for item in content:
            cols.append((Box(item), col_width))

        super().__init__(cols)


class TimingsBlock(ComposerItemInterface):
    """
    A compound composer item that displays the timings of a performance.

    Args:
        performance (Performance): The performance object containing the timings.
    """

    latecomerDisclaimer = "To limit disturbance to audiences and artists, we cannot guarantee that latecomers will be admitted to the performance. Latecomer policies are at the discretion of the production's Front of House team, who reserve the right to refuse entry to any person at their discretion."

    def __init__(self, performance) -> None:
        super().__init__()
        self.performance = performance
        self.doors = performance.doors_open.astimezone(
            performance.venue.address.timezone
        ).strftime("%A, %d %B %Y at %H:%M (%Z)")
        self.start = performance.start.astimezone(
            performance.venue.address.timezone
        ).strftime("%A, %d %B %Y at %H:%M (%Z)")

    def to_text(self):
        return f"\nTimings:\n\nDoors Open: {self.doors}\nPerformance Starts: {self.start}\n\n{self.latecomerDisclaimer}"

    def _stack_items(self):
        return [
            Heading(subsubtitle="Timings", title_icon="clock"),
            ListItem(
                title="Doors Open:",
                message=f"{self.doors}",
                title_icon="door-open",
                inline=True,
            ),
            ListItem(
                title="Performance Starts:",
                message=f"{self.start}",
                title_icon="play",
                inline=True,
            ),
            ListItem(message=self.latecomerDisclaimer),
        ]

    def to_html(self):
        return RowStack(self._stack_items()).to_html()

    def sub_items(self):
        subitems = [self]
        for item in self._stack_items():
            if hasattr(item, "sub_items"):
                subitems.extend(item.sub_items())
            else:
                subitems.append(item)
        return subitems


class BookingBlock(ComposerItemInterface):
    """
    A BookingBlock composer item.

    Args:
        booking (Booking): The booking object containing the details.
    """

    bookingInfo = "We operate a paperless ticketing system. Your tickets are available both below and in your online account. Please present your tickets on your phone at the event, or print them out at home. If you have any questions, please contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>."

    def __init__(self, booking) -> None:
        super().__init__()
        self.booking = booking

    def to_text(self):
        return f"\nYour Booking\n\nBooking Reference: {self.booking.reference}\n\n{self.bookingInfo}"

    def _stack_items(self):
        return [
            Heading(subsubtitle="Your Booking", title_icon="search"),
            ListItem(
                title="Booking Reference:",
                message=self.booking.reference,
                title_icon="barcode",
                inline=True,
            ),
            ListItem(message=self.bookingInfo, html_safe=True),
            ColStack(
                [
                    (
                        Button(self.booking.web_tickets_path, "View Tickets"),
                        50,
                    ),
                    (
                        Button(
                            f"/user/booking/{self.booking.reference}",
                            "View Booking",
                        ),
                        50,
                    ),
                ]
            ),
        ]

    def to_html(self):
        return RowStack(self._stack_items()).to_html()

    def sub_items(self):
        subitems = [self]
        for item in self._stack_items():
            if hasattr(item, "sub_items"):
                subitems.extend(item.sub_items())
            else:
                subitems.append(item)
        return subitems


class VenueAccessibilityBlock(ComposerItemInterface):
    """
    A VenueAccessibilityBlock composer item. Displays truncated venue accessibility information, and a link for more details.

    Args:
        venue (Venue): The venue object containing the accessibility details.
    """

    fallbackMessage = "If you have any accessibility concerns, or otherwise need help, please contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>."

    def __init__(self, venue) -> None:
        super().__init__()
        self.venue = venue
        accessibility_message_raw = (
            self.venue.accessibility_short
            or self.venue.accessibility_info
            or self.fallbackMessage
        )
        self.accessibility_message = strip_tags(accessibility_message_raw)
        if len(self.accessibility_message) > 200:
            self.accessibility_message = (
                self.accessibility_message[:200] + "..."
            )

    def to_text(self):
        return f"\nAccessibility Information:\n\n{strip_tags(self.accessibility_message)}"

    def _stack_items(self):

        stack = [
            Heading(
                subsubtitle="Venue Accessibility", title_icon="accessibility"
            ),
            ListItem(message=self.accessibility_message, html_safe=True),
        ]
        if self.venue.accessibility_info:
            stack.append(
                Button(
                    f"/venue/{self.venue.slug}/accessibility",
                    "View Further Information",
                )
            )
        return stack

    def to_html(self):
        return RowStack(self._stack_items()).to_html()

    def sub_items(self):
        subitems = [self]
        for item in self._stack_items():
            if hasattr(item, "sub_items"):
                subitems.extend(item.sub_items())
            else:
                subitems.append(item)
        return subitems


class VenueBlock(ComposerItemInterface):
    """
    A VenueBlock composer item.

    Provides quick information about a venue.

    Args:
        venue (Venue): The venue object containing the details.
    """

    def __init__(self, venue) -> None:
        super().__init__()
        self.venue = venue

    def _stack_items(self):
        # Build address parts, skipping any that are None or blank
        address_parts = [
            part
            for part in [
                getattr(self.venue.address, "building_name", None),
                getattr(self.venue.address, "building_number", None),
                getattr(self.venue.address, "street", None),
                getattr(self.venue.address, "city", None),
                getattr(self.venue.address, "postcode", None),
            ]
            if part and str(part).strip()
        ]
        address_str = ", ".join(address_parts)

        # Main venue information
        items = [
            Heading(subsubtitle="Venue Information", title_icon="city"),
            ListItem(
                title="Name:",
                message=self.venue.name,
                title_icon="building",
                inline=True,
            ),
            ListItem(
                title="Address:",
                message=address_str,
                title_icon="compass",
                inline=True,
            ),
        ]
        # Append What3Words if available
        if getattr(self.venue.address, "what3words", None):
            items.append(
                ListItem(
                    title="What3Words:",
                    message="<a href='https://what3words.com/{}' target='_blank'>{}</a>".format(
                        self.venue.address.what3words[
                            3:
                        ],  # what3words.com URLs omit the leading "///"
                        self.venue.address.what3words,
                    ),
                    title_icon="compass",
                    html_safe=True,
                    inline=True,
                )
            )
        # Always append an 'open in google maps' button
        maps_query = self.venue.name + (
            f", {self.venue.address.street}, {self.venue.address.city}"
            if self.venue.address
            and self.venue.address.street
            and self.venue.address.city
            else ""
        )
        maps_url = "https://maps.google.com/?q={}".format(
            quote_plus(maps_query)
        )
        items.append(Button(maps_url, "Open in Google Maps"))

        return items

    def to_html(self):
        return RowStack(self._stack_items()).to_html()

    def to_text(self):
        text = "\nVenue Information\n\n"
        text += f"Name: {self.venue.name}\n"
        text += f"Address: {self.venue.address.building_name}, {self.venue.address.building_number} {self.venue.address.street}, {self.venue.address.city}, {self.venue.address.postcode}\n"
        if getattr(self.venue, "what3words", None):
            text += f"What3Words: {self.venue.what3words}\n"
        return text.strip()

    def sub_items(self):
        subitems = [self]
        for item in self._stack_items():
            if hasattr(item, "sub_items"):
                subitems.extend(item.sub_items())
            else:
                subitems.append(item)
        return subitems


class BookingAccessibilityBlock(ComposerItemInterface):
    """
    A BookingAccessibilityBlock composer item.

    Provides quick information about booking accessibility.

    Args:
        booking (Booking): The booking object containing the details.
    """

    bookingAccessibilityInfo = "This information has been passed to the venue and/or production team, who may follow up with you if required. UOB Theatre is not responsible for this; this is the responsibility of the venue and production team, and it is not always possible to accommodate all requests. However, if your attendance depends on specific accessibility requirements to be met and you have not heard from the venue or production team in advance of 48 hours before the performance, we can try to follow up directly if you contact <a href='mailto:support@uobtheatre.com'>support@uobtheatre.com</a>."

    def __init__(self, booking) -> None:
        super().__init__()
        self.booking = booking

    def to_text(self):
        return f"\nBooking Accessibility Information:\n\n{strip_tags(self.booking.accessibility_info)}"

    def _stack_items(self):
        return [
            Heading(
                subsubtitle="Booking Accessibility Information",
                title_icon="accessibility",
            ),
            ListItem(
                title="You have provided the following accessibility information:",
                message=self.booking.accessibility_info,
                title_icon="info-circle",
            ),
            ListItem(message=self.bookingAccessibilityInfo, html_safe=True),
        ]

    def to_html(self):
        return RowStack(self._stack_items()).to_html()


class PaymentBlock(ComposerItemInterface):
    """
    A PaymentBlock composer item.

    Provides a standard layout for payment information.

    Args:
        payment (Payment): The payment object containing the details.
    """

    def __init__(self, payment) -> None:
        super().__init__()
        self.payment = payment

    def to_text(self):
        return f"\nPayment Information:\n\nAmount: £{self.payment.value}\nMethod: {self.payment.provider.description}"

    def _stack_items(self):
        return [
            Heading(subsubtitle="Payment Information", title_icon="trolley"),
            ListItem(
                message=f"{self.payment.value_currency} paid",
                message_icon="money",
            ),
            ListItem(
                message=f"{self.payment.provider.description}{(' - ID ' + self.payment.provider_transaction_id) if self.payment.provider_transaction_id else '' }",
                message_icon="card",
            ),
        ]

    def to_html(self):
        return RowStack(self._stack_items()).to_html()


class MailComposer(ComposerItemsContainer):
    """Compose a mail notificaiton"""

    @staticmethod
    def blank(content: list[ComposerItemInterface]) -> ComposerItemInterface:
        """Create a blank email, with the content (a list of elements to go in a RowStack) within.
        This will also add a footer component with extra button details."""

        # Prepare the footer for the buttons
        buttons = []
        for row in content:
            for item in ComposerItemInterface.collect_sub_items(row):
                if isinstance(item, Button):
                    buttons.append(ButtonHelpText(item.href, item.text))

        mail = MailComposer().row_stack(
            [
                Logo(),
                Box(RowStack(content), bg_col="white", mb=False),
                Footer(),
                # If there are buttons, add that after the footer
                Box(RowStack(buttons), bg_col="rgba(0,0,0,0.2)"),
            ]
        )

        return mail

    @staticmethod
    def text_only(
        title: str = "", message: str = "", html_safe: bool = False
    ) -> ComposerItemInterface:
        """Create an email that is text only. Takes in just a title and message.
        If html_safe == True, then this string will parse any given HTML; be careful,
        as if used improperly, this may open up scripting attacks."""
        return MailComposer.blank(
            [
                Box(
                    Heading(title=title, message=message, html_safe=html_safe),
                    bg_col="white",
                )
            ]
        )

    def get_complete_items(self):
        """Get the email body items (including any signature/signoff)"""
        return self.items

    def to_plain_text(self) -> str:
        """Generate the plain text version of the email"""
        return """{}""".format(
            "\n\n".join(
                [
                    item.to_text()
                    for item in self.get_complete_items()
                    if item.to_text()
                ]
            )
        )

    def to_html(self):
        """Generate the HTML version of the email"""
        content = """{}""".format(
            "\n".join(
                [item.to_html() or "" for item in self.get_complete_items()]
            )
        )

        email = get_template("new_base.html").render(
            {
                "content": content,
            }
        )

        return email

    def get_email(self, subject, to_email):
        msg = EmailMultiAlternatives(
            subject,
            self.to_plain_text(),
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
        )
        msg.attach_alternative(self.to_html(), "text/html")
        return msg

    def send(self, subject, to_email):
        """Send the email to the given email with the given subject"""
        msg = self.get_email(subject, to_email)
        msg.send()

    def sub_items(self):
        return [
            subItem for child in self.items for subItem in child.sub_items()
        ]


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
