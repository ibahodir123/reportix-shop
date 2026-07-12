from decimal import Decimal

from django.db import transaction
from django.db.models import F

from .models import Stock, StockMovement


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
):
    """
    Единственная точка изменения остатка: создаёт движение и атомарно
    обновляет кэш Stock. quantity: положительное — приход, отрицательное — расход.
    """
    quantity = Decimal(quantity)

    movement = StockMovement.objects.create(
        tenant=tenant,
        warehouse=warehouse,
        variant=variant,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=Decimal(unit_cost),
        reference=reference,
    )

    stock, _ = Stock.objects.select_for_update().get_or_create(
        warehouse=warehouse,
        variant=variant,
        defaults={"quantity": Decimal("0")},
    )
    stock.quantity = F("quantity") + quantity
    stock.save(update_fields=["quantity"])
    stock.refresh_from_db(fields=["quantity"])

    return movement
