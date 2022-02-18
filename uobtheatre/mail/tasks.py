import django
from config.celery import app
from django.core.mail import EmailMultiAlternatives, mail_admins
from django.core import mail

from uobtheatre.mail.composer import MailComposer
from django.conf import settings


@app.task
def send_emails(emails: list[dict[str, str]]):
    """Send emails async"""
    django_emails = []
    for email in emails:
        django_email = EmailMultiAlternatives(
            email["subject"],
            email["plain_text"],
            settings.DEFAULT_FROM_EMAIL,
            email["addresses"],
        )
        django_email.attach_alternative(email["html"], "text/html")
        django_emails.append(email)

    connection = mail.get_connection()
    connection.send_messages(django_emails)
    connection.close()

    # Send a copy of the email to the Django admins
    admin_mail = (
        MailComposer()
        .greeting()
        .line(f"The following mass email was sent {len(django_emails)} times.")
        .rule()
    )
    admin_mail.items += emails[0]["html"]
    admin_mail.rule()
    mail_admins(
        "Mass Email Sent: %s" % emails[0]["subject"],
        admin_mail.to_plain_text(),
        html_message=admin_mail.to_html(),
    )
