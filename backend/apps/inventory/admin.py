from django.contrib import admin

from .models import Receipt, ReceiptItem, Stock, StockMovement, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "is_active", "tenant")
    list_filter = ("tenant", "is_active")
    search_fields = ("name",)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("variant", "warehouse", "quantity")
    search_fields = ("variant__sku", "variant__product__name")
    readonly_fields = ("quantity",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "movement_type", "variant", "warehouse", "quantity", "tenant")
    list_filter = ("tenant", "movement_type")
    search_fields = ("variant__sku", "reference")
    date_hierarchy = "created_at"


class ReceiptItemInline(admin.TabularInline):
    model = ReceiptItem
    extra = 0
    readonly_fields = ("variant", "movement", "quantity", "purchase_price", "total")
    can_delete = False


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "warehouse", "supplier_name", "total_cost", "created_by", "tenant")
    list_filter = ("tenant", "warehouse")
    search_fields = ("supplier_name", "reference")
    date_hierarchy = "created_at"
    inlines = (ReceiptItemInline,)
    readonly_fields = ("total_cost", "created_at", "created_by", "client_uuid")
