from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.common.db import lock_tenant
from apps.inventory.models import StockMovement
from apps.inventory.services import record_movement

from .models import CashierShift, Sale, SaleItem

TWO = Decimal("0.01")


def _d(value):
    return Decimal(str(value))


@transaction.atomic
def open_shift(*, tenant, register, cashier, opening_cash=Decimal("0")):
    if register.tenant_id != tenant.id:
        raise ValidationError("Касса принадлежит другому бизнесу.")
    if CashierShift.objects.filter(register=register, status=CashierShift.STATUS_OPEN).exists():
        raise ValidationError("На этой кассе уже открыта смена.")
    return CashierShift.objects.create(
        tenant=tenant,
        register=register,
        cashier=cashier,
        opening_cash=_d(opening_cash),
        status=CashierShift.STATUS_OPEN,
    )


@transaction.atomic
def close_shift(*, shift, closing_cash=None):
    if shift.status != CashierShift.STATUS_OPEN:
        raise ValidationError("Смена уже закрыта.")

    shift.status = CashierShift.STATUS_CLOSED
    shift.closed_at = timezone.now()
    if closing_cash is not None:
        shift.closing_cash = _d(closing_cash)
    shift.save(update_fields=["status", "closed_at", "closing_cash", "updated_at"])
    return shift


def build_z_report(shift):
    """Сводка по смене (Z-отчёт): выручка, кол-во чеков, наличные/карта."""
    sales = shift.sales.filter(status=Sale.STATUS_COMPLETED)
    agg = sales.aggregate(
        count=Count("id"),
        total=Sum("total"),
        cash=Sum("paid_cash"),
        card=Sum("paid_card"),
        change=Sum("change"),
    )
    cash_collected = (agg["cash"] or Decimal("0")) - (agg["change"] or Decimal("0"))
    expected_cash = shift.opening_cash + cash_collected
    return {
        "shift_id": shift.pk,
        "status": shift.status,
        "opened_at": shift.opened_at,
        "closed_at": shift.closed_at,
        "sales_count": agg["count"] or 0,
        "revenue_total": agg["total"] or Decimal("0"),
        "paid_card": agg["card"] or Decimal("0"),
        "cash_collected": cash_collected,
        "opening_cash": shift.opening_cash,
        "expected_cash": expected_cash,
        "closing_cash": shift.closing_cash,
    }


def _next_sale_number(tenant):
    # Вызывается под блокировкой тенанта (lock_tenant) — гонки номеров нет.
    last = (
        Sale.objects.filter(tenant=tenant)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    return (last or 0) + 1


@transaction.atomic
def create_sale(
    *,
    tenant,
    shift,
    cashier,
    items,
    discount=Decimal("0"),
    payment_type=Sale.PAYMENT_CASH,
    paid_cash=Decimal("0"),
    paid_card=Decimal("0"),
    client_uuid=None,
):
    """
    Создаёт чек, фиксирует себестоимость и списывает товар со склада кассы
    (движение OUT на каждую позицию). Идемпотентно по client_uuid.

    Операции тенанта сериализуются через lock_tenant — устраняет гонки
    нумерации чеков и client_uuid при параллельных запросах.
    """
    lock_tenant(tenant)

    if client_uuid:
        existing = Sale.objects.filter(tenant=tenant, client_uuid=client_uuid).first()
        if existing is not None:
            return existing

    if shift.tenant_id != tenant.id:
        raise ValidationError("Смена принадлежит другому бизнесу.")
    if shift.status != CashierShift.STATUS_OPEN:
        raise ValidationError("Смена закрыта — продажа невозможна.")
    if not items:
        raise ValidationError("Чек пуст.")

    warehouse = shift.register.warehouse
    branch = shift.register.branch
    discount = _d(discount)
    paid_cash = _d(paid_cash)
    paid_card = _d(paid_card)

    subtotal = Decimal("0")
    prepared = []
    for row in items:
        variant = row["variant"]
        if variant.tenant_id != tenant.id:
            raise ValidationError("Вариант принадлежит другому бизнесу.")
        qty = _d(row["quantity"])
        if qty <= 0:
            raise ValidationError("Количество должно быть больше нуля.")
        price = _d(row["price"])
        line_discount = _d(row.get("discount", 0))
        line_total = (qty * price - line_discount).quantize(TWO)
        subtotal += line_total
        prepared.append(
            {
                "variant": variant,
                "quantity": qty,
                "price": price,
                "discount": line_discount,
                "cost_price": _d(variant.purchase_price),
                "total": line_total,
            }
        )

    total = (subtotal - discount).quantize(TWO)
    if total < 0:
        raise ValidationError("Скидка превышает сумму чека.")

    if paid_cash < 0 or paid_card < 0:
        raise ValidationError("Суммы оплаты не могут быть отрицательными.")

    paid = paid_cash + paid_card
    if paid < total:
        raise ValidationError("Оплата меньше суммы чека.")
    # Переплата картой недопустима: сдачу дают только наличными, поэтому
    # оплата картой не может превышать сумму чека. Это гарантирует, что
    # change = paid - total ≤ paid_cash (сдача не превышает внесённые наличные).
    if paid_card > total:
        raise ValidationError("Оплата картой превышает сумму чека (переплата картой недопустима).")
    change = (paid - total).quantize(TWO)

    sale = Sale.objects.create(
        tenant=tenant,
        branch=branch,
        shift=shift,
        warehouse=warehouse,
        cashier=cashier,
        number=_next_sale_number(tenant),
        client_uuid=client_uuid,
        subtotal=subtotal.quantize(TWO),
        discount=discount,
        total=total,
        payment_type=payment_type,
        paid_cash=paid_cash,
        paid_card=paid_card,
        change=change,
    )

    for row in prepared:
        SaleItem.objects.create(sale=sale, **row)
        record_movement(
            tenant=tenant,
            warehouse=warehouse,
            variant=row["variant"],
            movement_type=StockMovement.TYPE_OUT,
            quantity=-row["quantity"],
            unit_cost=row["cost_price"],
            reference=f"Чек №{sale.number}",
        )

    return sale
