import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIClient

from apps.catalog.models import Product, Unit, Variant
from apps.inventory.models import Stock, StockMovement, Warehouse
from apps.inventory.services import record_movement
from apps.tenants.models import Branch, Membership, Tenant, User

from .models import CashRegister, Return, ReturnItem
from .services import create_return, create_sale, open_shift


def _stock(warehouse, variant):
    s = Stock.objects.filter(warehouse=warehouse, variant=variant).first()
    return s.quantity if s else Decimal("0")


class ReturnServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="c", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.wh = Warehouse.objects.create(tenant=self.tenant, branch=self.branch, name="Склад")
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.v1 = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("40"), sale_price=Decimal("100")
        )
        self.v2 = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-2", purchase_price=Decimal("30"), sale_price=Decimal("100")
        )
        for v in (self.v1, self.v2):
            record_movement(
                tenant=self.tenant, warehouse=self.wh, variant=v,
                movement_type=StockMovement.TYPE_IN, quantity=Decimal("100"),
            )
        self.register = CashRegister.objects.create(
            tenant=self.tenant, branch=self.branch, warehouse=self.wh, name="Касса 1"
        )
        self.shift = open_shift(tenant=self.tenant, register=self.register, cashier=self.user)
        self.sale = create_sale(
            tenant=self.tenant, shift=self.shift, cashier=self.user,
            items=[
                {"variant": self.v1, "quantity": Decimal("5"), "price": Decimal("100")},
                {"variant": self.v2, "quantity": Decimal("3"), "price": Decimal("100")},
            ],
            paid_cash=Decimal("800"),
        )
        self.si1 = self.sale.items.get(variant=self.v1)
        self.si2 = self.sale.items.get(variant=self.v2)

    def _return(self, item_qtys, **kw):
        items = [{"sale_item": si, "quantity": Decimal(q)} for si, q in item_qtys]
        return create_return(
            tenant=self.tenant, sale=self.sale, created_by=self.user, shift=self.shift,
            items=items, **kw,
        )

    def test_full_return_restocks(self):
        doc = self._return([(self.si1, "5")], payment_type=Return.PAYMENT_CASH)
        self.assertEqual(doc.refund_total, Decimal("500.00"))
        self.assertEqual(doc.refund_cash, Decimal("500.00"))
        self.assertEqual(_stock(self.wh, self.v1), Decimal("100.000"))  # 95 + 5
        self.assertTrue(
            StockMovement.objects.filter(
                movement_type=StockMovement.TYPE_RETURN_IN, variant=self.v1
            ).exists()
        )

    def test_cannot_exceed_across_returns(self):
        self._return([(self.si1, "3")], payment_type=Return.PAYMENT_CASH)
        with self.assertRaises(DRFValidationError):
            self._return([(self.si1, "3")], payment_type=Return.PAYMENT_CASH)  # 3+3 > 5

    def test_excess_single_rejected(self):
        with self.assertRaises(DRFValidationError):
            self._return([(self.si1, "6")], payment_type=Return.PAYMENT_CASH)
        self.assertEqual(Return.objects.count(), 0)
        self.assertEqual(_stock(self.wh, self.v1), Decimal("95.000"))

    def test_atomic_rollback_on_bad_line(self):
        with self.assertRaises(DRFValidationError):
            self._return([(self.si1, "2"), (self.si2, "999")], payment_type=Return.PAYMENT_CASH)
        self.assertEqual(Return.objects.count(), 0)
        self.assertFalse(
            StockMovement.objects.filter(movement_type=StockMovement.TYPE_RETURN_IN).exists()
        )
        self.assertEqual(_stock(self.wh, self.v1), Decimal("95.000"))
        self.assertEqual(_stock(self.wh, self.v2), Decimal("97.000"))

    def test_idempotent(self):
        cu = uuid.uuid4()
        first = self._return([(self.si1, "2")], payment_type=Return.PAYMENT_CASH, client_uuid=cu)
        second = self._return([(self.si1, "2")], payment_type=Return.PAYMENT_CASH, client_uuid=cu)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Return.objects.count(), 1)
        self.assertEqual(_stock(self.wh, self.v1), Decimal("97.000"))  # 95 + 2 (один раз)

    def test_mixed_money_mismatch(self):
        with self.assertRaises(DRFValidationError):
            self._return(
                [(self.si1, "2")], payment_type=Return.PAYMENT_MIXED,
                refund_cash=Decimal("100"), refund_card=Decimal("50"),  # 150 != 200
            )
        good = self._return(
            [(self.si1, "2")], payment_type=Return.PAYMENT_MIXED,
            refund_cash=Decimal("120"), refund_card=Decimal("80"),
        )
        self.assertEqual(good.refund_total, Decimal("200.00"))

    def test_return_is_immutable(self):
        doc = self._return([(self.si1, "1")], payment_type=Return.PAYMENT_CASH)
        fresh = Return.objects.get(pk=doc.pk)
        fresh.refund_total = Decimal("1")
        with self.assertRaises(DjangoValidationError):
            fresh.save()
        with self.assertRaises(DjangoValidationError):
            Return.objects.get(pk=doc.pk).delete()
        item = doc.items.first()
        item.quantity = Decimal("9")
        with self.assertRaises(DjangoValidationError):
            item.save()
        with self.assertRaises(DjangoValidationError):
            doc.items.first().delete()

    def test_duplicate_sale_item_grouped_and_summed(self):
        # Дубли одной позиции в запросе суммируются в одну строку возврата.
        doc = self._return(
            [(self.si1, "2"), (self.si1, "2")], payment_type=Return.PAYMENT_CASH
        )
        self.assertEqual(doc.items.count(), 1)
        self.assertEqual(doc.items.first().quantity, Decimal("4.000"))
        self.assertEqual(_stock(self.wh, self.v1), Decimal("99.000"))  # 95 + 4

    def test_duplicate_sale_item_total_exceeds_rejected(self):
        # 3 + 3 = 6 > продано 5 — отклоняется по СУММАРНОМУ количеству.
        with self.assertRaises(DRFValidationError):
            self._return(
                [(self.si1, "3"), (self.si1, "3")], payment_type=Return.PAYMENT_CASH
            )
        self.assertEqual(Return.objects.count(), 0)
        self.assertEqual(_stock(self.wh, self.v1), Decimal("95.000"))


class ReturnDiscountTests(TestCase):
    """Возврат с учётом скидок: полный = sale.total, частичные ≤ sale.total."""

    def setUp(self):
        self.user = User.objects.create_user(username="c", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.wh = Warehouse.objects.create(tenant=self.tenant, branch=self.branch, name="Склад")
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.v1 = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("40"), sale_price=Decimal("100")
        )
        self.v2 = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-2", purchase_price=Decimal("30"), sale_price=Decimal("100")
        )
        for v in (self.v1, self.v2):
            record_movement(
                tenant=self.tenant, warehouse=self.wh, variant=v,
                movement_type=StockMovement.TYPE_IN, quantity=Decimal("100"),
            )
        self.register = CashRegister.objects.create(
            tenant=self.tenant, branch=self.branch, warehouse=self.wh, name="Касса 1"
        )
        self.shift = open_shift(tenant=self.tenant, register=self.register, cashier=self.user)
        # v1: 2×100 − строчная 20 = 180; v2: 1×100 = 100; − скидка на чек 30 → total 250.
        self.sale = create_sale(
            tenant=self.tenant, shift=self.shift, cashier=self.user,
            items=[
                {"variant": self.v1, "quantity": Decimal("2"), "price": Decimal("100"), "discount": Decimal("20")},
                {"variant": self.v2, "quantity": Decimal("1"), "price": Decimal("100")},
            ],
            discount=Decimal("30"),
            paid_cash=Decimal("250"),
        )
        self.si1 = self.sale.items.get(variant=self.v1)
        self.si2 = self.sale.items.get(variant=self.v2)

    def _return(self, item_qtys, **kw):
        items = [{"sale_item": si, "quantity": Decimal(q)} for si, q in item_qtys]
        return create_return(
            tenant=self.tenant, sale=self.sale, created_by=self.user, shift=self.shift,
            items=items, **kw,
        )

    def test_full_return_equals_sale_total(self):
        self.assertEqual(self.sale.total, Decimal("250.00"))
        doc = self._return([(self.si1, "2"), (self.si2, "1")], payment_type=Return.PAYMENT_CASH)
        self.assertEqual(doc.refund_total, self.sale.total)  # 250.00

    def test_partial_returns_never_exceed_total(self):
        r1 = self._return([(self.si1, "1")], payment_type=Return.PAYMENT_CASH)
        r2 = self._return([(self.si1, "1")], payment_type=Return.PAYMENT_CASH)
        r3 = self._return([(self.si2, "1")], payment_type=Return.PAYMENT_CASH)
        running = Decimal("0")
        for r in (r1, r2, r3):
            running += r.refund_total
            self.assertLessEqual(running, self.sale.total)  # никогда не превышает
        self.assertEqual(running, self.sale.total)  # в сумме ровно sale.total

    def test_cannot_exceed_after_full_line(self):
        self._return([(self.si1, "2")], payment_type=Return.PAYMENT_CASH)  # позиция закрыта
        with self.assertRaises(DRFValidationError):
            self._return([(self.si1, "1")], payment_type=Return.PAYMENT_CASH)


class ReturnApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass12345")
        self.cashier1 = User.objects.create_user(username="c1", password="pass12345")
        self.cashier2 = User.objects.create_user(username="c2", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.owner)
        self.branch1 = Branch.objects.create(tenant=self.tenant, name="Ф1")
        self.branch2 = Branch.objects.create(tenant=self.tenant, name="Ф2")
        self.wh1 = Warehouse.objects.create(tenant=self.tenant, branch=self.branch1, name="Склад 1")
        Membership.objects.create(tenant=self.tenant, user=self.owner, role=Membership.ROLE_OWNER)
        Membership.objects.create(
            tenant=self.tenant, user=self.cashier1, role=Membership.ROLE_CASHIER, branch=self.branch1
        )
        Membership.objects.create(
            tenant=self.tenant, user=self.cashier2, role=Membership.ROLE_CASHIER, branch=self.branch1
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.variant = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("40"), sale_price=Decimal("100")
        )
        record_movement(
            tenant=self.tenant, warehouse=self.wh1, variant=self.variant,
            movement_type=StockMovement.TYPE_IN, quantity=Decimal("100"),
        )
        self.reg1 = CashRegister.objects.create(
            tenant=self.tenant, branch=self.branch1, warehouse=self.wh1, name="Касса 1"
        )
        self.shift1 = open_shift(tenant=self.tenant, register=self.reg1, cashier=self.cashier1)
        self.sale = create_sale(
            tenant=self.tenant, shift=self.shift1, cashier=self.cashier1,
            items=[{"variant": self.variant, "quantity": Decimal("5"), "price": Decimal("100")}],
            paid_cash=Decimal("500"),
        )
        self.si = self.sale.items.first()

    def _client(self, user):
        c = APIClient()
        c.force_login(user)
        return c

    def _payload(self, shift=None, qty=2, cu=None):
        body = {
            "sale": self.sale.id,
            "payment_type": "cash",
            "items": [{"sale_item": self.si.id, "quantity": qty}],
        }
        if shift is not None:
            body["shift"] = shift
        if cu is not None:
            body["client_uuid"] = str(cu)
        return body

    def test_owner_can_return_any_sale(self):
        resp = self._client(self.owner).post("/api/sales/returns/", self._payload(), format="json")
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_cashier_return_own_sale_own_shift(self):
        resp = self._client(self.cashier1).post(
            "/api/sales/returns/", self._payload(shift=self.shift1.id), format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_cashier_cannot_return_other_cashier_sale(self):
        # cashier2 open own shift, но продажа принадлежит cashier1.
        reg1b = CashRegister.objects.create(
            tenant=self.tenant, branch=self.branch1, warehouse=self.wh1, name="Касса 1B"
        )
        shift2 = open_shift(tenant=self.tenant, register=reg1b, cashier=self.cashier2)
        resp = self._client(self.cashier2).post(
            "/api/sales/returns/", self._payload(shift=shift2.id), format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_cashier_needs_own_open_shift(self):
        resp = self._client(self.cashier1).post(
            "/api/sales/returns/", self._payload(), format="json"  # без shift
        )
        self.assertEqual(resp.status_code, 403)

    def test_lookup_returns_returnable(self):
        resp = self._client(self.cashier1).get(
            f"/api/sales/returns/lookup/?number={self.sale.number}"
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        item = resp.json()["items"][0]
        self.assertEqual(item["sale_item"], self.si.id)
        self.assertEqual(item["returnable"], "5.000")

    def test_history_is_read_only(self):
        created = self._client(self.owner).post(
            "/api/sales/returns/", self._payload(), format="json"
        )
        rid = created.json()["id"]
        detail = f"/api/sales/returns/{rid}/"
        self.assertEqual(self._client(self.owner).patch(detail, {}, format="json").status_code, 405)
        self.assertEqual(self._client(self.owner).delete(detail).status_code, 405)

    def test_idempotent_api(self):
        cu = uuid.uuid4()
        first = self._client(self.owner).post("/api/sales/returns/", self._payload(cu=cu), format="json")
        second = self._client(self.owner).post("/api/sales/returns/", self._payload(cu=cu), format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Return.objects.count(), 1)
