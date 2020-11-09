import uuid
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save
from rest_framework.authtoken.models import Token


class Society(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Production(models.Model):
    name = models.CharField(max_length=255)
    society = models.ForeignKey(Society, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
