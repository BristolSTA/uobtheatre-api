import os
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from uobtheatre.mail.composer import MailComposer


class Command(BaseCommand):
    """
    Django management command to send a test email to a specified address or a testmail.app inbox.
    """

    help = "Send a test email to the specified address"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="The email address to send the test email to. If not provided, a random testmail.app address will be used.",
        )
        parser.add_argument(
            "--namespace",
            type=str,
            help="The namespace to use for the testmail.app address. If not provided, 'testmail' will be used.",
        )
        parser.add_argument(
            "--tag",
            type=str,
            help="The tag to use for the testmail.app address. If not provided, a random UUID will be generated.",
        )
        parser.add_argument(
            "--expect-aws",
            action="store_true",
            help="Expect the email to be sent via AWS SES.",
        )
        parser.add_argument(
            "--check-receipt",
            action="store_true",
            help="Check that the email was received by the testmail.app inbox. This requires a namespace AND an API key to be set in the environment variable TESTMAIL_API_KEY.",
        )

    def handle(
        self, *args, **options
    ):  # pylint: disable=unused-argument, too-many-locals, too-many-branches, too-many-branches
        """
        This is a smoke test to ensure that the email sending functionality works.
        It does not check the contents of the email, only that it can be sent without error.
        In CI, this is paired with testemail to check reciept of the email.
        """
        tag = options["tag"] if options["tag"] else str(uuid4())

        if options["email"]:
            target_email = options["email"]
        elif options["namespace"]:
            target_email = (
                options["namespace"] + "." + tag + "@inbox.testmail.app"
            )
        else:
            # Raise an error if no email or namespace is provided
            raise CommandError(
                "You must provide at least an email (--email) or, for testmail, a namespace (--namespace)."
            )

        if (
            options["expect_aws"]
            and settings.EMAIL_BACKEND
            != "anymail.backends.amazon_ses.EmailBackend"
        ):
            raise CommandError(
                "You have specified --expect-aws, but the EMAIL_BACKEND is not set to anymail.backends.amazon_ses.EmailBackend."
            )

        self.stdout.write(
            self.style.NOTICE(
                f"Using the {settings.EMAIL_BACKEND} backend to send a test email"
            )
        )

        composer = MailComposer()

        composer.line("This is a test email from the UOB Theatre system.")

        try:
            # .send() returns 1 if there was an error sending the email, and 0 if it was sent successfully
            if composer.send("Test Email from UOB Theatre", target_email):
                raise CommandError(
                    "Failed to send test email, but no exception was raised."
                )
            self.stdout.write(
                self.style.SUCCESS("Successfully sent test email")
            )
        except Exception as e:
            raise CommandError(f"Failed to send test email: {e}") from e

        if options["check_receipt"]:
            if not options["namespace"]:
                raise CommandError(
                    "You must provide a namespace (--namespace) to check receipt of the email."
                )
            if not (api_key := os.getenv("TESTMAIL_API_KEY")):
                raise CommandError(
                    "You must set the TESTMAIL_API_KEY environment variable to check receipt of the email."
                )

            import json

            import requests

            self.stdout.write(
                self.style.NOTICE(
                    "Checking receipt of test email in testmail.app inbox..."
                )
            )

            endpoint = "https://api.testmail.app/api/json"
            params = {
                "namespace": options["namespace"],
                "apikey": api_key,
                "livequery": "true",
                "tag": tag,
            }

            for attempt in range(5):
                response = requests.get(endpoint, params=params, timeout=64)

                if response.status_code == 200:
                    break
                if response.status_code == 307:
                    # Still waiting
                    self.stdout.write(
                        self.style.NOTICE(
                            f"Waiting for test email to be received... (attempt {attempt + 1}/5)"
                        )
                    )
                else:
                    raise CommandError(
                        f"Failed to check receipt of test email: {response.status_code} {response.text}"
                    )

            data = response.json()

            if not (
                data.get("result", "fail") == "success"
                and data.get("emails", [])
            ):
                raise CommandError(
                    f"Testmail could not find the email, and responded with {json.dumps(data, indent=2)}."
                )

            email = data["emails"][0]

            if (
                email["subject"] == "Test Email from UOB Theatre"
                and email["to"] == target_email
            ):
                self.stdout.write(
                    self.style.SUCCESS(
                        "Successfully received test email in testmail.app inbox"
                    )
                )
            else:
                raise CommandError(
                    f"Testmail received an email, but it did not match the expected subject or recipient. Received: {json.dumps(email, indent=2)}"
                )
