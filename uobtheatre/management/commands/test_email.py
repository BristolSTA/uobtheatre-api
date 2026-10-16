from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from uobtheatre.mail.composer import MailComposer

class Command(BaseCommand):
    help = "Send a test email to the specified address"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="The email address to send the test email to. If not provided, a random testmail.app address will be used.",
        ),
        parser.add_argument(
            "--namespace",
            type=str,
            help="The namespace to use for the testmail.app address. If not provided, 'testmail' will be used.",
        ),
        parser.add_argument(
            "--tag",
            type=str,
            help="The tag to use for the testmail.app address. If not provided, a random UUID will be generated.",
        ),
        parser.add_argument(
            "--expect-aws",
            action="store_true",
            help="Expect the email to be sent via AWS SES.",
        )

    def handle(self, *args, **options):  # pylint: disable=unused-argument
        """
        This is a smoke test to ensure that the email sending functionality works.
        It does not check the contents of the email, only that it can be sent without error.
        In CI, this is paired with testemail to check reciept of the email.
        """
        if options["email"]:
            target_email = options["email"]
        elif options["namespace"]:
            target_email = (
                options["namespace"] + "." + options["tag"] if options["tag"] else str(uuid4()) + "@inbox.testmail.app"
            )
        else:
            # Raise an error if no email or namespace is provided
            raise CommandError(
                "You must provide at least an email (--email) or, for testmail, a namespace (--namespace)."
            )

        if options["expect_aws"] and settings.EMAIL_BACKEND != "anymail.backends.amazon_ses.EmailBackend":
            raise CommandError(
                "You have specified --expect-aws, but the EMAIL_BACKEND is not set to anymail.backends.amazon_ses.EmailBackend."
            )

        self.stdout.write(
            self.style.NOTICE(f"Using the {settings.EMAIL_BACKEND} backend to send a test email")
        )

        composer = MailComposer()

        composer.line("This is a test email from the UOB Theatre system.")

        try:
            if not composer.send("Test Email from UOB Theatre", target_email):
                raise CommandError("Failed to send test email, but no exception was raised.")
            self.stdout.write(
                self.style.SUCCESS(f"Successfully sent test email")
            )
        except Exception as e:
            raise CommandError(f"Failed to send test email: {e}")