from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.common.db import lock_tenant
from apps.common.exceptions import InsufficientStock

from .models import Receipt, ReceiptItem, Stock, StockMovement

TWO = Decimal("0.01")


@transaction.atomic
def record_movement(
    *,
    tenant,
    warehouse,
    variant,
    movement_type,
    quantity,
    unit_cost=Decimal("0"),
    reference="",
    allow_negative=False,
):
    """
    Единственная точка изменения остатка. quantity: положительное — приход,
    отрицательное — расход.

    Остаток блокируется (SELECT ... FOR UPDATE); проверка достаточности и
    списание выполняются атомарно. Если расход уводит остаток в минус и
    allow_negative=False — поднимается InsufficientStock (409); движение НЕ
    создаётся (продажа в минус запрещена, частичных движений нет).
    """
    quantity = Decimal(quantity)

    stock, _ = Stock.objects.select_for_update().get_or_create(
        warehouse=warehouse,
        variant=variant,
        defaults={"quantity": Decimal("0")},
    )
    new_quantity = stock.quantity + quantity
    if new_quantity < 0 and not allow_negative:
        raise InsufficientStock(
            f"Недостаточно остатка «{variant}»: есть {stock.quantity}, "
            f"требуется {abs(quantity)}."
        )

    movement = StockMovement.objects.create(
        tenant=tenant,
        warehouse=warehouse,
        variant=variant,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=Decimal(unit_cost),
        reference=reference,
    )
    stock.quantity = new_quantity
    stock.save(update_fields=["quantity"])

    return movement


@transaction.atomic
def create_receipt(
    *,
    tenant,
    warehouse,
    created_by,
    items,
    supplier_name="",
    reference="",
    client_uuid=None,
):
    """
    Проводит приёмку: для каждой позиции создаёт движение IN через
    record_movement и обновляет остаток. Всё в одной транзакции — при ошибке
    в любой строке откатывается целиком. Идемпотентно по client_uuid.
    """
    # Сериализуем операции тенанта — устраняем гонку client_uuid.
    lock_tenant(tenant)

    if client_uuid:
        existing = Receipt.objects.filter(tenant=tenant, client_uuid=client_uuid).first()
        if existing is not None:
            return existing

    if warehouse.tenant_id != tenant.id:
        raise ValidationError({"warehouse": "Склад принадлежит другому бизнесу."})
    if not items:
        raise ValidationError("Документ приёмки пуст.")

    receipt = Receipt.objects.create(
        tenant=tenant,
        warehouse=warehouse,
        created_by=created_by,
        supplier_name=supplier_name or "",
        reference=reference or "",
        client_uuid=client_uuid,
        total_cost=Decimal("0"),
    )

    total = Decimal("0")
    for row in items:
        variant = row["variant"]
        if variant.tenant_id != tenant.id:
            raise ValidationError({"variant": "Вариант принадлежит другому бизнесу."})
        quantity = Decimal(row["quantity"])
        if quantity <= 0:
            raise ValidationError({"quantity": "Количество должно быть больше нуля."})
        price = Decimal(row.get("purchase_price") or 0)
        line_total = (quantity * price).quantize(TWO)

        movement = record_movement(
            tenant=tenant,
            warehouse=warehouse,
            variant=variant,
            movement_type=StockMovement.TYPE_IN,
            quantity=quantity,
            unit_cost=price,
            reference=f"Приёмка #{receipt.pk}",
        )
        ReceiptItem.objects.create(
            receipt=receipt,
            variant=variant,
            movement=movement,
            quantity=quantity,
            purchase_price=price,
            total=line_total,
        )
        total += line_total

    receipt.total_cost = total.quantize(TWO)
    receipt.save(update_fields=["total_cost", "updated_at"])
    return receipt
