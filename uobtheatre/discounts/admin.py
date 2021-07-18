from django.contrib import admin

from uobtheatre.discounts.models import ConcessionType, Discount, DiscountRequirement

admin.site.register(ConcessionType)


class DiscountRequirementInline(admin.StackedInline):
    model = DiscountRequirement
    extra = 1


class DiscountAdmin(admin.ModelAdmin):
    inlines = [DiscountRequirementInline]


admin.site.register(Discount, DiscountAdmin)
