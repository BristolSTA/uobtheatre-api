from django.contrib import admin, messages

from uobtheatre.payments.models import Transaction
from uobtheatre.utils.exceptions import SquareException


@admin.action(description="Refresh payment from square")  # type: ignore
def refresh_from_square(modeladmin, request, queryset):
    """
    Refresh payment details from provider
    """
    successful_updates = 0
    for payment in queryset.all():
        try:
            payment.sync_transaction_with_provider()
            successful_updates += 1
        except SquareException as exc:
            modeladmin.message_user(
                request,
                f"Error updating payment {payment.id}: {exc.message}",
                level=messages.ERROR,
            )
    modeladmin.message_user(request, f"{successful_updates} payments refreshed.")


class TransactionAdmin(admin.ModelAdmin):
    actions = [refresh_from_square]
    list_filter = (
        "type",
        "status",
        ("provider_fee", admin.EmptyFieldListFilter),  # type: ignore
    )


admin.site.register(Transaction, TransactionAdmin)
