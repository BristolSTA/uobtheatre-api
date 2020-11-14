import pytest
from django.db import models

from uobtheatre.utils.models import SoftDeletionMixin, TimeStampedMixin

# class ExampleModel(models.Model, TimeStampedMixin):
#    app_label = "example"
#
#
# @pytest.mark.django_db
# def test_timestamped_mixin():
#
#    # create a class with the mixin
#    assert hasattr(ExampleModel(), "created_at")
#    assert hasattr(ExampleModel(), "updated_at")
