from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from graphql_auth.models import UserStatus

from .models import User

admin.site.register(UserStatus)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """User Admin"""

    ordering = ("email",)
    exclude = ("username",)
    search_fields = [
        "first_name",
        "last_name",
        "email",
    ]
    fieldsets = (
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "email", "password")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "email", "password1", "password2")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )
