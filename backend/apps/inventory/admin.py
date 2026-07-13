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
    can_delete = False
    readonly_fields = ("variant", "movement", "quantity", "purchase_price", "total")

    # Позиции проведённой приёмки нельзя добавлять/менять/удалять.
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "warehouse", "supplier_name", "total_cost", "created_by", "tenant")
    list_filter = ("tenant", "warehouse")
    search_fields = ("supplier_name", "reference")
    date_hierarchy = "created_at"
    inlines = (ReceiptItemInline,)
    # Проведённая приёмка неизменяема — все поля только для чтения.
    readonly_fields = (
        "tenant",
        "warehouse",
        "created_by",
        "supplier_name",
        "reference",
        "client_uuid",
        "total_cost",
        "created_at",
        "updated_at",
    )

    # Создание — только через endpoint проведения; удаление запрещено.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # View-only режим: изменение запрещено, просмотр сохраняется. Django
    # рендерит форму read-only без кнопок «Сохранить»/«…и продолжить»/«Удалить».
    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True
