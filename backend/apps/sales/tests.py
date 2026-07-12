import uuid
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Product, Unit, Variant
from apps.inventory.models import Stock, StockMovement, Warehouse
from apps.inventory.services import record_movement
from apps.tenants.models import Branch, Tenant, User

from .models import CashierShift, CashRegister, Sale
from .services import build_z_report, close_shift, create_sale, open_shift


class SaleFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cashier", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Основной"
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Футболка", unit=self.unit)
        self.variant = Variant.objects.create(
            tenant=self.tenant,
            product=product,
            sku="TSH-BL-L",
            name="Синий / L",
            purchase_price=Decimal("45000"),
            sale_price=Decimal("79000"),
        )
        self.register = CashRegister.objects.create(
            tenant=self.tenant, branch=self.branch, warehouse=self.warehouse, name="Касса 1"
        )
        # Заводим начальный остаток 10 шт.
        record_movement(
            tenant=self.tenant,
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=StockMovement.TYPE_IN,
            quantity=Decimal("10"),
            unit_cost=Decimal("45000"),
        )

    def _open(self):
        return open_shift(
            tenant=self.tenant,
            register=self.register,
            cashier=self.user,
            opening_cash=Decimal("100000"),
        )

    def test_sale_decrements_stock_and_computes_totals(self):
        shift = self._open()
        sale = create_sale(
            tenant=self.tenant,
            shift=shift,
            cashier=self.user,
            items=[{"variant": self.variant, "quantity": Decimal("2"), "price": Decimal("79000")}],
            payment_type=Sale.PAYMENT_CASH,
            paid_cash=Decimal("160000"),
        )
        self.assertEqual(sale.total, Decimal("158000.00"))
        self.assertEqual(sale.change, Decimal("2000.00"))
        self.assertEqual(sale.items.count(), 1)
        self.assertEqual(sale.items.first().cost_price, Decimal("45000.00"))

        stock = Stock.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(stock.quantity, Decimal("8.000"))

    def test_idempotent_by_client_uuid(self):
        shift = self._open()
        cu = uuid.uuid4()
        kwargs = dict(
            tenant=self.tenant,
            shift=shift,
            cashier=self.user,
            items=[{"variant": self.variant, "quantity": Decimal("1"), "price": Decimal("79000")}],
            paid_cash=Decimal("79000"),
            client_uuid=cu,
        )
        first = create_sale(**kwargs)
        second = create_sale(**kwargs)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Sale.objects.count(), 1)

    def test_one_open_shift_per_register(self):
        self._open()
        with self.assertRaises(Exception):
            self._open()

    def test_z_report_after_close(self):
        shift = self._open()
        create_sale(
            tenant=self.tenant,
            shift=shift,
            cashier=self.user,
            items=[{"variant": self.variant, "quantity": Decimal("1"), "price": Decimal("79000")}],
            paid_cash=Decimal("79000"),
        )
        shift = close_shift(shift=shift, closing_cash=Decimal("179000"))
        report = build_z_report(shift)
        self.assertEqual(report["sales_count"], 1)
        self.assertEqual(report["revenue_total"], Decimal("79000.00"))
        self.assertEqual(report["expected_cash"], Decimal("179000.00"))
