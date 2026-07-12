from django.conf import settings
from django.db import models

from apps.common.models import TenantOwnedModel


class CashRegister(TenantOwnedModel):
    """Касса (физическая точка расчёта) внутри магазина."""

    branch = models.ForeignKey(
        "tenants.Branch", on_delete=models.CASCADE, related_name="registers"
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="registers",
        help_text="Склад, с которого списываются проданные товары",
    )
    name = models.CharField(max_length=255, verbose_name="Наименование")
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "branch", "name")
        verbose_name = "Касса"
        verbose_name_plural = "Кассы"

    def __str__(self):
        return self.name


class CashierShift(TenantOwnedModel):
    """Смена кассира: открытие/закрытие, инкассация, основа Z-отчёта."""

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = (
        (STATUS_OPEN, "Открыта"),
        (STATUS_CLOSED, "Закрыта"),
    )

    register = models.ForeignKey(CashRegister, on_delete=models.PROTECT, related_name="shifts")
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shifts"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    opening_cash = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            # Одна открытая смена на кассу.
            models.UniqueConstraint(
                fields=["register"],
                condition=models.Q(status="open"),
                name="uniq_open_shift_per_register",
            ),
        ]
        verbose_name = "Смена"
        verbose_name_plural = "Смены"

    def __str__(self):
        return f"Смена #{self.pk} ({self.register}) — {self.get_status_display()}"


class Sale(TenantOwnedModel):
    """Чек продажи."""

    PAYMENT_CASH = "cash"
    PAYMENT_CARD = "card"
    PAYMENT_MIXED = "mixed"
    PAYMENT_CHOICES = (
        (PAYMENT_CASH, "Наличные"),
        (PAYMENT_CARD, "Карта"),
        (PAYMENT_MIXED, "Смешанная"),
    )

    STATUS_COMPLETED = "completed"
    STATUS_VOID = "void"
    STATUS_CHOICES = (
        (STATUS_COMPLETED, "Проведён"),
        (STATUS_VOID, "Аннулирован"),
    )

    branch = models.ForeignKey("tenants.Branch", on_delete=models.PROTECT, related_name="sales")
    shift = models.ForeignKey(CashierShift, on_delete=models.PROTECT, related_name="sales")
    warehouse = models.ForeignKey(
        "inventory.Warehouse", on_delete=models.PROTECT, related_name="sales"
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales"
    )
    number = models.PositiveIntegerField(verbose_name="Номер чека")
    # Идемпотентность: повтор при обрыве сети не задваивает продажу.
    client_uuid = models.UUIDField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default=PAYMENT_CASH)
    paid_cash = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_card = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    change = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_COMPLETED)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="uniq_sale_number_per_tenant"),
            models.UniqueConstraint(
                fields=["tenant", "client_uuid"],
                condition=models.Q(client_uuid__isnull=False),
                name="uniq_sale_client_uuid_per_tenant",
            ),
        ]
        verbose_name = "Продажа"
        verbose_name_plural = "Продажи"

    def __str__(self):
        return f"Чек №{self.number}"


class SaleItem(models.Model):
    """Позиция чека. cost_price фиксируется на момент продажи (для маржи)."""

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.PROTECT, related_name="sale_items"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    price = models.DecimalField(max_digits=18, decimal_places=2)
    discount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Позиция чека"
        verbose_name_plural = "Позиции чека"

    def __str__(self):
        return f"{self.variant} × {self.quantity}"
