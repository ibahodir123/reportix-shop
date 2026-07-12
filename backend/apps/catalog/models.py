from django.db import models

from apps.common.models import TenantOwnedModel


class Category(TenantOwnedModel):
    name = models.CharField(max_length=255, verbose_name="Наименование")
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name", "parent")
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Brand(TenantOwnedModel):
    name = models.CharField(max_length=255, verbose_name="Наименование")

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"

    def __str__(self):
        return self.name


class Unit(TenantOwnedModel):
    """Единица измерения (шт, кг, м...). allow_fractional — для весового товара."""

    name = models.CharField(max_length=50, verbose_name="Наименование")
    short_name = models.CharField(max_length=16, verbose_name="Сокращение")
    allow_fractional = models.BooleanField(default=False, verbose_name="Дробное количество")

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "short_name")
        verbose_name = "Единица измерения"
        verbose_name_plural = "Единицы измерения"

    def __str__(self):
        return self.short_name


class Product(TenantOwnedModel):
    name = models.CharField(max_length=255, verbose_name="Наименование")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="products")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["tenant", "name"])]
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self):
        return self.name


class Variant(TenantOwnedModel):
    """
    Вариант товара (размер/цвет). У «плоского» товара — один дефолтный вариант.
    Остаток и продажа всегда идут на уровне варианта.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=64, verbose_name="Артикул")
    name = models.CharField(
        max_length=255, blank=True, verbose_name="Название варианта", help_text="Например: Синий / L"
    )
    attributes = models.JSONField(
        default=dict, blank=True, verbose_name="Атрибуты", help_text='{"size": "L", "color": "синий"}'
    )
    purchase_price = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="Закупочная цена"
    )
    sale_price = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="Цена продажи"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        ordering = ["product__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "sku"], name="uniq_variant_sku_per_tenant"),
        ]
        verbose_name = "Вариант"
        verbose_name_plural = "Варианты"

    def __str__(self):
        return f"{self.product.name} — {self.name}" if self.name else self.product.name


class Barcode(models.Model):
    """Штрихкод варианта. Вариантов штрихкодов может быть несколько."""

    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name="barcodes")
    code = models.CharField(max_length=64, db_index=True, verbose_name="Штрихкод")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["variant", "code"], name="uniq_barcode_per_variant"),
        ]
        verbose_name = "Штрихкод"
        verbose_name_plural = "Штрихкоды"

    def __str__(self):
        return self.code
