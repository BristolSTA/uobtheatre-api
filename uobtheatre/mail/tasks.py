from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives, mail_admins

from config.celery import app


@app.task
def send_emails(email_addresses: list[str], subject: str, plain_text: str, html: str):
    """Send emails async"""

    from uobtheatre.mail.composer import MailComposer

    django_emails = []
    for address in email_addresses:
        django_email = EmailMultiAlternatives(
            subject,
            plain_text,
            settings.DEFAULT_FROM_EMAIL,
            [address],
        )
        django_email.attach_alternative(html, "text/html")
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
        .html(html)
        .rule()
    )
    mail_admins(
        "Mass Email Sent: %s" % subject,
        admin_mail.to_plain_text(),
        html_message=admin_mail.to_html(),
    )
