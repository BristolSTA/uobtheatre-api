
import factory
from django_celery_results.models import TaskResult


class TaskResultFactory(factory.django.DjangoModelFactory):

    status = "SUCCESS"
    task_name = factory.Faker("sentence", nb_words=2)
    task_id = factory.Faker("uuid4")

    class Meta:
        model = TaskResult
