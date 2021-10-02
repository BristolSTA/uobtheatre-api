from django.db import models


class Reports(models.Model):
    """A pseudo model to store report permissions"""

    class Meta:

        managed = False  # No database table creation or deletion  \
        # operations will be performed for this model.

        default_permissions = ()  # disable "add", "change", "delete"
        # and "view" default permissions

        permissions = (("finance_reports", "Finance Reports"),)
