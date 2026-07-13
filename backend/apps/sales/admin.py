from django.contrib import admin

from apps.inventory.admin import ReadOnlyAdminMixin

from .models import CashierShift, CashRegister, Return, ReturnItem, Sale, SaleItem


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


class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 0
    can_delete = False
    readonly_fields = ("sale_item", "variant", "movement", "quantity", "price", "total")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Return)
class ReturnAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "created_at", "sale", "refund_total", "payment_type", "created_by", "tenant")
    list_filter = ("tenant", "payment_type")
    date_hierarchy = "created_at"
    inlines = (ReturnItemInline,)
    readonly_fields = (
        "tenant",
        "sale",
        "branch",
        "warehouse",
        "shift",
        "created_by",
        "client_uuid",
        "payment_type",
        "refund_cash",
        "refund_card",
        "refund_total",
        "created_at",
    )
