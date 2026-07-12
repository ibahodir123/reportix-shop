from django.contrib import admin

from .models import Barcode, Brand, Category, Product, Unit, Variant


class BarcodeInline(admin.TabularInline):
    model = Barcode
    extra = 1


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 1
    fields = ("sku", "name", "purchase_price", "sale_price", "is_active")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "tenant")
    list_filter = ("tenant",)
    search_fields = ("name",)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant")
    list_filter = ("tenant",)
    search_fields = ("name",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "allow_fractional", "tenant")
    list_filter = ("tenant",)
    search_fields = ("name", "short_name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "brand", "unit", "is_active", "tenant")
    list_filter = ("tenant", "is_active", "category", "brand")
    search_fields = ("name",)
    inlines = (VariantInline,)


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("__str__", "sku", "purchase_price", "sale_price", "is_active", "tenant")
    list_filter = ("tenant", "is_active")
    search_fields = ("sku", "name", "product__name")
    inlines = (BarcodeInline,)
