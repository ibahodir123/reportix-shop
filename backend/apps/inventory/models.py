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
