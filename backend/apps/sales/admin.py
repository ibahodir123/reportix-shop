from django.contrib import admin

from .models import CashierShift, CashRegister, Sale, SaleItem


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "warehouse", "is_active", "tenant")
    list_filter = ("tenant", "is_active")
    search_fields = ("name",)


@admin.register(CashierShift)
class CashierShiftAdmin(admin.ModelAdmin):
    list_display = ("id", "register", "cashier", "status", "opened_at", "closed_at")
    list_filter = ("tenant", "status")
    date_hierarchy = "opened_at"


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("variant", "quantity", "price", "discount", "cost_price", "total")
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("number", "created_at", "total", "payment_type", "status", "cashier", "tenant")
    list_filter = ("tenant", "payment_type", "status")
    search_fields = ("number",)
    date_hierarchy = "created_at"
    inlines = (SaleItemInline,)
    readonly_fields = (
        "number",
        "subtotal",
        "total",
        "change",
        "created_at",
    )
