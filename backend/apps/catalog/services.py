"""Сервисы каталога: быстрое создание товара из голосового черновика."""

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import record_movement

from .models import Barcode, Brand, Category, Product, Unit, Variant


def _resolve_unit(tenant, unit_id):
    if unit_id:
        unit = Unit.objects.filter(tenant=tenant, id=unit_id).first()
        if unit is None:
            raise ValidationError({"unit": "Единица измерения не найдена."})
        return unit
    # По умолчанию — «шт».
    unit, _ = Unit.objects.get_or_create(
        tenant=tenant, short_name="шт", defaults={"name": "Штука"}
    )
    return unit


def _resolve_fk(model, tenant, pk, field):
    if not pk:
        return None
    obj = model.objects.filter(tenant=tenant, id=pk).first()
    if obj is None:
        raise ValidationError({field: "Объект не найден или принадлежит другому бизнесу."})
    return obj


def _gen_sku(tenant):
    n = Variant.objects.filter(tenant=tenant).count() + 1
    sku = f"AUTO-{n}"
    while Variant.objects.filter(tenant=tenant, sku=sku).exists():
        n += 1
        sku = f"AUTO-{n}"
    return sku


def _variant_name(color, size):
    parts = [p for p in (color, size) if p]
    return " / ".join(parts)


@transaction.atomic
def quick_create_product(*, tenant, data):
    """
    Создаёт Product + Variant и, если задано количество и склад, приходует
    товар движением IN. Возвращает созданный Product.
    """
    unit = _resolve_unit(tenant, data.get("unit"))
    category = _resolve_fk(Category, tenant, data.get("category"), "category")
    brand = _resolve_fk(Brand, tenant, data.get("brand"), "brand")

    product = Product.objects.create(
        tenant=tenant, name=data["name"], unit=unit, category=category, brand=brand
    )

    color = (data.get("color") or "").strip()
    size = (data.get("size") or "").strip()
    attributes = {}
    if color:
        attributes["color"] = color
    if size:
        attributes["size"] = size

    variant = Variant.objects.create(
        tenant=tenant,
        product=product,
        sku=(data.get("sku") or "").strip() or _gen_sku(tenant),
        name=_variant_name(color, size),
        attributes=attributes,
        purchase_price=data.get("purchase_price") or Decimal("0"),
        sale_price=data.get("sale_price") or Decimal("0"),
    )

    barcode = (data.get("barcode") or "").strip()
    if barcode:
        Barcode.objects.create(variant=variant, code=barcode)

    quantity = data.get("quantity") or Decimal("0")
    if quantity and quantity > 0:
        warehouse_id = data.get("warehouse")
        if not warehouse_id:
            raise ValidationError({"warehouse": "Для прихода количества укажите склад."})
        warehouse = Warehouse.objects.filter(tenant=tenant, id=warehouse_id).first()
        if warehouse is None:
            raise ValidationError({"warehouse": "Склад не найден."})
        record_movement(
            tenant=tenant,
            warehouse=warehouse,
            variant=variant,
            movement_type=StockMovement.TYPE_IN,
            quantity=quantity,
            unit_cost=variant.purchase_price,
            reference="Голосовой ввод",
        )

    return product
