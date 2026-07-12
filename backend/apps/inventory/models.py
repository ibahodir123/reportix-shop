from django.conf import settings
from django.db import models

from apps.common.models import TenantOwnedModel, TimeStampedModel


class Warehouse(TenantOwnedModel):
    branch = models.ForeignKey(
        "tenants.Branch", on_delete=models.CASCADE, related_name="warehouses"
    )
    name = models.CharField(max_length=255, verbose_name="Наименование")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "branch", "name")
        verbose_name = "Склад"
        verbose_name_plural = "Склады"

    def __str__(self):
        return self.name


class Stock(models.Model):
    """
    Текущий остаток варианта на складе — КЭШ. Источник истины = StockMovement.
    Обновляется только через apps.inventory.services.record_movement().
    """

    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="stocks")
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.CASCADE, related_name="stocks"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["warehouse", "variant"], name="uniq_stock_wh_variant"),
        ]
        verbose_name = "Остаток"
        verbose_name_plural = "Остатки"

    def __str__(self):
        return f"{self.variant} @ {self.warehouse}: {self.quantity}"


class StockMovement(TimeStampedModel):
    """Движение товара — единственный способ изменить остаток (полный аудит)."""

    TYPE_IN = "in"
    TYPE_OUT = "out"
    TYPE_WRITEOFF = "writeoff"
    TYPE_TRANSFER = "transfer"
    TYPE_ADJUST = "adjust"
    TYPE_CHOICES = (
        (TYPE_IN, "Приход"),
        (TYPE_OUT, "Расход"),
        (TYPE_WRITEOFF, "Списание"),
        (TYPE_TRANSFER, "Перемещение"),
        (TYPE_ADJUST, "Корректировка"),
    )

    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="stock_movements"
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="movements")
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.PROTECT, related_name="movements"
    )
    movement_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    quantity = models.DecimalField(
        max_digits=18, decimal_places=3, help_text="+ приход / − расход"
    )
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    reference = models.CharField(max_length=255, blank=True, help_text="Документ-основание")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["warehouse", "variant"]),
        ]
        verbose_name = "Движение товара"
        verbose_name_plural = "Движения товара"

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.variant}: {self.quantity}"


class Receipt(TenantOwnedModel):
    """Документ приёмки товара на склад. История приёмок сохраняется."""

    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="receipts")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="receipts"
    )
    supplier_name = models.CharField(max_length=255, blank=True, verbose_name="Поставщик")
    reference = models.CharField(max_length=255, blank=True, verbose_name="Основание")
    # Идемпотентность: повтор одного запроса не задваивает приёмку.
    client_uuid = models.UUIDField(null=True, blank=True)
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="uniq_receipt_client_uuid_per_tenant",
            ),
        ]
        verbose_name = "Приёмка"
        verbose_name_plural = "Приёмки"

    def __str__(self):
        return f"Приёмка #{self.pk}"


class ReceiptItem(models.Model):
    """Позиция документа приёмки (привязана к созданному движению IN)."""

    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.PROTECT, related_name="receipt_items"
    )
    movement = models.ForeignKey(
        StockMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipt_items",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    purchase_price = models.DecimalField(max_digits=18, decimal_places=2)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Позиция приёмки"
        verbose_name_plural = "Позиции приёмки"

    def __str__(self):
        return f"{self.variant} × {self.quantity}"
