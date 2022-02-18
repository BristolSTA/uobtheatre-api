from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, mail_admins

from config.celery import app


@app.task
def send_emails(emails: list[dict[str, str]]):
    """Send emails async"""

    from uobtheatre.mail.composer import MailComposer

    django_emails = []
    for email in emails:
        django_email = EmailMultiAlternatives(
            email["subject"],
            email["plain_text"],
            settings.DEFAULT_FROM_EMAIL,
            email["addresses"],
        )
        django_email.attach_alternative(email["html"], "text/html")
        django_emails.append(django_email)

    connection = mail.get_connection()
    connection.send_messages(django_emails)
    connection.close()

    # Send a copy of the email to the Django admins
    admin_mail = (
        MailComposer()
        .greeting()
        .line(f"The following mass email was sent {len(django_emails)} times.")
        .rule()
        .html(emails[0]["html"])
        .rule()
    )
    mail_admins(
        "Mass Email Sent: %s" % emails[0]["subject"],
        admin_mail.to_plain_text(),
        html_message=admin_mail.to_html(),
    )
