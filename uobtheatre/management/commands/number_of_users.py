from django.core.management.base import BaseCommand

from uobtheatre.users.models import User


class Command(BaseCommand):
    help = "Return number of users"

    def handle(self, *args, **options):  # pylint: disable=unused-argument
        number_of_users = User.objects.count()
        self.stdout.write(self.style.SUCCESS(number_of_users))
