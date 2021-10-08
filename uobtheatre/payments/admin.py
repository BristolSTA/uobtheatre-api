from django.contrib import admin

from uobtheatre.payments.models import Payment


@admin.action(description="Refresh payment from square")  # type: ignore
def refresh_from_square(modeladmin, request, queryset):
    for payment in queryset.all():
        payment.update_from_square()
        modeladmin.message_user(request, f"{queryset.count()} payments updated.")


class PaymentAdmin(admin.ModelAdmin):
    actions = [refresh_from_square]


admin.site.register(Payment, PaymentAdmin)
