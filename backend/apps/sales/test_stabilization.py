import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Product, Unit, Variant
from apps.common.exceptions import InsufficientStock
from apps.inventory.models import Stock, StockMovement, Warehouse
from apps.inventory.services import record_movement
from apps.tenants.models import Branch, Tenant, User

from .models import CashierShift, CashRegister, Sale
from .services import create_sale, open_shift


def _base_setup(obj, initial_stock="20"):
    obj.user = User.objects.create_user(username="cashier", password="pass12345")
    obj.tenant = Tenant.objects.create(name="Магазин", owner=obj.user)
    obj.branch = Branch.objects.create(tenant=obj.tenant, name="Центр")
    obj.warehouse = Warehouse.objects.create(
        tenant=obj.tenant, branch=obj.branch, name="Основной"
    )
    obj.unit = Unit.objects.create(tenant=obj.tenant, name="Штука", short_name="шт")
    product = Product.objects.create(tenant=obj.tenant, name="Товар", unit=obj.unit)
    obj.variant = Variant.objects.create(
        tenant=obj.tenant, product=product, sku="A-1", purchase_price=Decimal("40")
    )
    obj.register = CashRegister.objects.create(
        tenant=obj.tenant, branch=obj.branch, warehouse=obj.warehouse, name="Касса 1"
    )
    record_movement(
        tenant=obj.tenant,
        warehouse=obj.warehouse,
        variant=obj.variant,
        movement_type=StockMovement.TYPE_IN,
        quantity=Decimal(initial_stock),
    )
    obj.shift = open_shift(
        tenant=obj.tenant, register=obj.register, cashier=obj.user
    )


class SalePaymentTests(TestCase):
    def setUp(self):
        _base_setup(self)

    def _sale(self, **kw):
        return create_sale(
            tenant=self.tenant,
            shift=self.shift,
            cashier=self.user,
            items=[{"variant": self.variant, "quantity": Decimal("1"), "price": Decimal("100")}],
            **kw,
        )

    def _stock(self):
        s = Stock.objects.filter(warehouse=self.warehouse, variant=self.variant).first()
        return s.quantity if s else Decimal("0")

    def test_cash_change(self):
        sale = self._sale(payment_type=Sale.PAYMENT_CASH, paid_cash=Decimal("150"))
        self.assertEqual(sale.total, Decimal("100.00"))
        self.assertEqual(sale.change, Decimal("50.00"))

    def test_card_exact_no_change(self):
        sale = self._sale(payment_type=Sale.PAYMENT_CARD, paid_card=Decimal("100"))
        self.assertEqual(sale.change, Decimal("0.00"))

    def test_card_overpay_rejected(self):
        with self.assertRaises(ValidationError):
            self._sale(payment_type=Sale.PAYMENT_CARD, paid_card=Decimal("200"))
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(self._stock(), Decimal("20.000"))

    def test_mixed_change_only_from_cash(self):
        # card 60 (<= total 100), cash 50 → сдача 10, вся с наличных.
        sale = self._sale(
            payment_type=Sale.PAYMENT_MIXED,
            paid_card=Decimal("60"),
            paid_cash=Decimal("50"),
        )
        self.assertEqual(sale.change, Decimal("10.00"))
        self.assertLessEqual(sale.change, sale.paid_cash)

    def test_mixed_card_overpay_rejected(self):
        with self.assertRaises(ValidationError):
            self._sale(
                payment_type=Sale.PAYMENT_MIXED,
                paid_card=Decimal("150"),
                paid_cash=Decimal("0"),
            )
        self.assertEqual(Sale.objects.count(), 0)

    def test_oversell_blocked(self):
        with self.assertRaises(InsufficientStock):
            create_sale(
                tenant=self.tenant,
                shift=self.shift,
                cashier=self.user,
                items=[
                    {"variant": self.variant, "quantity": Decimal("100"), "price": Decimal("100")}
                ],
                paid_cash=Decimal("10000"),
            )
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(self._stock(), Decimal("20.000"))
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.TYPE_OUT).count(), 0
        )


class SaleConcurrencyTests(TransactionTestCase):
    """Требует БД с реальными блокировками (PostgreSQL)."""

    def setUp(self):
        _base_setup(self)

    def _worker(self, client_uuid):
        try:
            shift = CashierShift.objects.select_related(
                "register__warehouse", "register__branch"
            ).get(pk=self.shift.pk)
            return create_sale(
                tenant=self.tenant,
                shift=shift,
                cashier=self.user,
                items=[{"variant": self.variant, "quantity": Decimal("1"), "price": Decimal("100")}],
                paid_cash=Decimal("100"),
                client_uuid=client_uuid,
            )
        finally:
            connection.close()

    def test_same_uuid_no_duplicates(self):
        cu = uuid.uuid4()
        with ThreadPoolExecutor(max_workers=5) as ex:
            list(ex.map(lambda _: self._worker(cu), range(5)))
        self.assertEqual(Sale.objects.filter(client_uuid=cu).count(), 1)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.TYPE_OUT).count(), 1
        )

    def test_distinct_uuids_unique_numbers(self):
        with ThreadPoolExecutor(max_workers=5) as ex:
            list(ex.map(lambda _: self._worker(uuid.uuid4()), range(5)))
        numbers = sorted(Sale.objects.values_list("number", flat=True))
        self.assertEqual(numbers, [1, 2, 3, 4, 5])
