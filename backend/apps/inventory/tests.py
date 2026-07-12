import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Product, Unit, Variant
from apps.tenants.models import Branch, Membership, Tenant, User

from .models import Receipt, Stock, StockMovement, Warehouse

URL = "/api/inventory/receipts/"


class ReceiptApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        Membership.objects.create(
            tenant=self.tenant, user=self.user, role=Membership.ROLE_OWNER
        )
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Основной"
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.v1 = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("100")
        )
        self.v2 = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-2", purchase_price=Decimal("50")
        )

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _stock(self, variant):
        s = Stock.objects.filter(warehouse=self.warehouse, variant=variant).first()
        return s.quantity if s else Decimal("0")

    def test_multiline_receipt_success(self):
        resp = self.client.post(
            URL,
            {
                "warehouse": self.warehouse.id,
                "supplier_name": "ООО Поставка",
                "items": [
                    {"variant": self.v1.id, "quantity": "2", "purchase_price": "100"},
                    {"variant": self.v2.id, "quantity": "3", "purchase_price": "50"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        receipt = Receipt.objects.get(tenant=self.tenant)
        self.assertEqual(receipt.items.count(), 2)
        self.assertEqual(receipt.total_cost, Decimal("350.00"))
        self.assertEqual(self._stock(self.v1), Decimal("2.000"))
        self.assertEqual(self._stock(self.v2), Decimal("3.000"))
        self.assertEqual(
            StockMovement.objects.filter(
                tenant=self.tenant, movement_type=StockMovement.TYPE_IN
            ).count(),
            2,
        )

    def test_atomic_rollback_on_bad_line(self):
        # Вторая строка невалидна (кол-во 0) — вся приёмка должна откатиться,
        # включая уже созданное движение по первой строке.
        resp = self.client.post(
            URL,
            {
                "warehouse": self.warehouse.id,
                "items": [
                    {"variant": self.v1.id, "quantity": "5", "purchase_price": "100"},
                    {"variant": self.v2.id, "quantity": "0", "purchase_price": "50"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Receipt.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(self._stock(self.v1), Decimal("0"))

    def test_reject_foreign_tenant_variant(self):
        other_user = User.objects.create_user(username="o", password="pass12345")
        other_tenant = Tenant.objects.create(name="Чужой", owner=other_user)
        other_unit = Unit.objects.create(
            tenant=other_tenant, name="Штука", short_name="шт"
        )
        other_product = Product.objects.create(
            tenant=other_tenant, name="Чужой товар", unit=other_unit
        )
        foreign_variant = Variant.objects.create(
            tenant=other_tenant, product=other_product, sku="F-1"
        )
        resp = self.client.post(
            URL,
            {
                "warehouse": self.warehouse.id,
                "items": [{"variant": foreign_variant.id, "quantity": "1", "purchase_price": "10"}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Receipt.objects.count(), 0)

    def test_reject_invalid_quantity(self):
        resp = self.client.post(
            URL,
            {
                "warehouse": self.warehouse.id,
                "items": [{"variant": self.v1.id, "quantity": "-2", "purchase_price": "100"}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Receipt.objects.count(), 0)

    def test_idempotent_by_client_uuid(self):
        cu = str(uuid.uuid4())
        body = {
            "warehouse": self.warehouse.id,
            "client_uuid": cu,
            "items": [{"variant": self.v1.id, "quantity": "4", "purchase_price": "100"}],
        }
        first = self.client.post(URL, body, format="json")
        second = self.client.post(URL, body, format="json")
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(movement_type=StockMovement.TYPE_IN).count(), 1
        )
        self.assertEqual(self._stock(self.v1), Decimal("4.000"))

    def test_requires_tenant(self):
        other = User.objects.create_user(username="notenant", password="pass12345")
        client = APIClient()
        client.force_authenticate(other)
        resp = client.post(
            URL,
            {"warehouse": self.warehouse.id, "items": [{"variant": self.v1.id, "quantity": "1"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
