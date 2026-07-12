from django.contrib import admin

from .models import Stock, StockMovement, Warehouse


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
