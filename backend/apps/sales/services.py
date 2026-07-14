from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.common.db import lock_tenant
from apps.inventory.models import StockMovement
from apps.inventory.services import record_movement

from .models import CashierShift, Return, ReturnItem, Sale, SaleItem

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


def returned_qty_for(sale_item):
    """Сколько уже возвращено по позиции чека (сумма прошлых возвратов)."""
    agg = ReturnItem.objects.filter(sale_item=sale_item).aggregate(s=Sum("quantity"))
    return agg["s"] or Decimal("0")


def _sale_allocations(sale):
    """
    Распределяет sale.total (после строчных скидок и скидки на чек) по позициям.
    Сумма распределения строго равна sale.total (остаток округления — последней
    позиции). Это гарантирует, что полный возврат всех позиций даёт ровно
    sale.total, а сумма частичных возвратов его не превышает.
    """
    items = list(sale.items.all().order_by("id"))
    allocations = {}
    if not items:
        return allocations

    subtotal = sale.subtotal or Decimal("0")
    total = sale.total or Decimal("0")
    if subtotal > 0:
        running = Decimal("0")
        for sale_item in items[:-1]:
            alloc = (sale_item.total * total / subtotal).quantize(TWO)
            allocations[sale_item.id] = alloc
            running += alloc
        allocations[items[-1].id] = (total - running).quantize(TWO)
    else:
        for sale_item in items:
            allocations[sale_item.id] = Decimal("0")
    return allocations


def _cumulative_refund(alloc, sold, returned):
    """Пропорциональный возврат для `returned` единиц позиции (округление 2 зн.)."""
    if sold <= 0:
        return Decimal("0")
    return (alloc * returned / sold).quantize(TWO)


@transaction.atomic
def create_return(
    *,
    tenant,
    sale,
    created_by,
    shift,
    items,
    payment_type=Return.PAYMENT_CASH,
    refund_cash=Decimal("0"),
    refund_card=Decimal("0"),
    client_uuid=None,
):
    """
    Проводит возврат по чеку: возвращает товар на склад движением RETURN_IN и
    фиксирует сумму/способ возврата денег. Всё атомарно. Идемпотентно по
    client_uuid. Нельзя вернуть больше проданного с учётом прошлых возвратов.
    """
    lock_tenant(tenant)

    if client_uuid:
        existing = Return.objects.filter(tenant=tenant, client_uuid=client_uuid).first()
        if existing is not None:
            return existing

    if sale.tenant_id != tenant.id:
        raise ValidationError("Чек принадлежит другому бизнесу.")
    if not items:
        raise ValidationError("Не выбраны позиции для возврата.")

    # Группируем повторяющиеся позиции в запросе и суммируем количество.
    grouped = {}  # sale_item.id -> [sale_item, qty]
    for row in items:
        sale_item = row["sale_item"]
        if sale_item.sale_id != sale.id:
            raise ValidationError("Позиция не принадлежит этому чеку.")
        qty = _d(row["quantity"])
        if qty <= 0:
            raise ValidationError("Количество возврата должно быть больше нуля.")
        if sale_item.id in grouped:
            grouped[sale_item.id][1] += qty
        else:
            grouped[sale_item.id] = [sale_item, qty]

    # Возврат считаем с учётом скидок (строчных и на чек).
    allocations = _sale_allocations(sale)

    prepared = []
    refund_total = Decimal("0")
    for sale_item, qty in grouped.values():
        already = returned_qty_for(sale_item)
        available = sale_item.quantity - already
        if qty > available:
            raise ValidationError(
                f"Нельзя вернуть больше проданного: доступно {available}, запрошено {qty}."
            )
        alloc = allocations.get(sale_item.id, Decimal("0"))
        # Дельта пропорционального возврата: гарантирует, что полный возврат
        # позиции даёт ровно её долю в sale.total, а частичные не превышают её.
        refund_line = _cumulative_refund(
            alloc, sale_item.quantity, already + qty
        ) - _cumulative_refund(alloc, sale_item.quantity, already)
        prepared.append((sale_item, qty, sale_item.price, refund_line, sale_item.cost_price))
        refund_total += refund_line
    refund_total = refund_total.quantize(TWO)

    # Способ и сумма возврата денег.
    if payment_type == Return.PAYMENT_CASH:
        refund_cash, refund_card = refund_total, Decimal("0")
    elif payment_type == Return.PAYMENT_CARD:
        refund_cash, refund_card = Decimal("0"), refund_total
    elif payment_type == Return.PAYMENT_MIXED:
        refund_cash = _d(refund_cash)
        refund_card = _d(refund_card)
        if refund_cash < 0 or refund_card < 0:
            raise ValidationError("Суммы возврата не могут быть отрицательными.")
        if (refund_cash + refund_card).quantize(TWO) != refund_total:
            raise ValidationError("Сумма возврата денег не совпадает со стоимостью позиций.")
    else:
        raise ValidationError("Неизвестный способ возврата денег.")

    warehouse = sale.warehouse
    document = Return.objects.create(
        tenant=tenant,
        sale=sale,
        branch=sale.branch,
        warehouse=warehouse,
        shift=shift,
        created_by=created_by,
        client_uuid=client_uuid,
        payment_type=payment_type,
        refund_cash=refund_cash,
        refund_card=refund_card,
        refund_total=refund_total,
    )

    for sale_item, qty, price, line_total, cost_price in prepared:
        movement = record_movement(
            tenant=tenant,
            warehouse=warehouse,
            variant=sale_item.variant,
            movement_type=StockMovement.TYPE_RETURN_IN,
            quantity=qty,
            unit_cost=cost_price,
            reference=f"Возврат #{document.pk}",
        )
        ReturnItem.objects.create(
            document=document,
            sale_item=sale_item,
            variant=sale_item.variant,
            movement=movement,
            quantity=qty,
            price=price,
            total=line_total,
        )

    return document
