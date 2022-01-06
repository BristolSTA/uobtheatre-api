from typing import List

from django.db.models import Model

from uobtheatre.mail.composer import MailComposer
from uobtheatre.users.models import User
from uobtheatre.utils.lang import pluralize


def payable_refund_initiated_email(authorizing_user: User, models: List[Model]):
    return (
        MailComposer()
        .greeting()
        .line(
            f"Refund(s) have been initiated for the following {pluralize('item', models)}:"
        )
        .line(
            ", ".join(
                f"{model.__class__.__name__} {model} ({model.pk})" for model in models
            )
        )
        .line(
            f"This action was requested by {authorizing_user.full_name} ({authorizing_user.email})"
        )
    )
