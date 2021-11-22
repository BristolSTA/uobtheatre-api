from django.contrib import admin

from uobtheatre.payments.models import Payment


@admin.action(description="Refresh payment from square")  # type: ignore
def refresh_from_square(modeladmin, request, queryset):
    for payment in queryset.all():
        payment.sync_payment_with_provider()
    modeladmin.message_user(request, f"{queryset.count()} payments refreshed.")


class PaymentAdmin(admin.ModelAdmin):
    actions = [refresh_from_square]
    list_filter = (
        "type",
        "status",
        ("provider_fee", admin.EmptyFieldListFilter),  # type: ignore
    )


admin.site.register(Payment, PaymentAdmin)
