from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Product, Unit, Variant
from apps.inventory.models import StockMovement, Warehouse
from apps.inventory.services import record_movement
from apps.tenants.models import Branch, Membership, Tenant, User


class RoleAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass12345")
        self.manager = User.objects.create_user(username="manager", password="pass12345")
        self.cashier = User.objects.create_user(username="cashier", password="pass12345")
        self.nomember = User.objects.create_user(username="nobody", password="pass12345")

        self.tenant = Tenant.objects.create(name="Магазин", owner=self.owner)
        self.branch1 = Branch.objects.create(tenant=self.tenant, name="Филиал 1")
        self.branch2 = Branch.objects.create(tenant=self.tenant, name="Филиал 2")
        self.wh1 = Warehouse.objects.create(tenant=self.tenant, branch=self.branch1, name="Склад 1")
        self.wh2 = Warehouse.objects.create(tenant=self.tenant, branch=self.branch2, name="Склад 2")

        Membership.objects.create(tenant=self.tenant, user=self.owner, role=Membership.ROLE_OWNER)
        Membership.objects.create(tenant=self.tenant, user=self.manager, role=Membership.ROLE_MANAGER)
        Membership.objects.create(
            tenant=self.tenant, user=self.cashier, role=Membership.ROLE_CASHIER, branch=self.branch1
        )

        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.variant = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("40"),
            sale_price=Decimal("100"),
        )
        record_movement(
            tenant=self.tenant, warehouse=self.wh1, variant=self.variant,
            movement_type=StockMovement.TYPE_IN, quantity=Decimal("100"),
        )

        from apps.sales.models import CashRegister

        self.register1 = CashRegister.objects.create(
            tenant=self.tenant, branch=self.branch1, warehouse=self.wh1, name="Касса 1"
        )
        self.register2 = CashRegister.objects.create(
            tenant=self.tenant, branch=self.branch2, warehouse=self.wh2, name="Касса 2"
        )

    def _client(self, user):
        c = APIClient()
        c.force_login(user)
        return c

    # --- /me/ ---------------------------------------------------------------
    def test_me_returns_role_and_branch(self):
        body = self._client(self.cashier).get("/api/auth/me/").json()
        self.assertEqual(body["role"], "cashier")
        self.assertEqual(body["branch"], self.branch1.id)

        owner_body = self._client(self.owner).get("/api/auth/me/").json()
        self.assertEqual(owner_body["role"], "owner")
        self.assertIsNone(owner_body["branch"])

    # --- Каталог / товары ---------------------------------------------------
    def test_products_owner_manager_ok_cashier_forbidden(self):
        self.assertEqual(self._client(self.owner).get("/api/catalog/products/").status_code, 200)
        self.assertEqual(self._client(self.manager).get("/api/catalog/products/").status_code, 200)
        self.assertEqual(self._client(self.cashier).get("/api/catalog/products/").status_code, 403)

    def test_variants_read_all_roles_write_restricted(self):
        # Чтение вариантов (поиск в POS) — всем ролям.
        for user in (self.owner, self.manager, self.cashier):
            self.assertEqual(
                self._client(user).get("/api/catalog/variants/").status_code, 200
            )
        # Создание варианта кассиру запрещено.
        resp = self._client(self.cashier).post(
            "/api/catalog/variants/",
            {"product": self.variant.product_id, "sku": "X-9"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_quick_product_manager_ok_cashier_forbidden(self):
        payload = {"name": "Новый", "sale_price": "1000"}
        self.assertEqual(
            self._client(self.manager).post("/api/catalog/quick-product/", payload, format="json").status_code,
            201,
        )
        self.assertEqual(
            self._client(self.cashier).post("/api/catalog/quick-product/", payload, format="json").status_code,
            403,
        )

    def test_voice_manager_ok_cashier_forbidden(self):
        payload = {"text": "Ручка продажа 5 тысяч 3 штук"}
        self.assertEqual(
            self._client(self.manager).post("/api/voice/parse-product/", payload, format="json").status_code,
            200,
        )
        self.assertEqual(
            self._client(self.cashier).post("/api/voice/parse-product/", payload, format="json").status_code,
            403,
        )

    # --- Склад / приёмка ----------------------------------------------------
    def test_warehouses_cashier_forbidden(self):
        self.assertEqual(self._client(self.manager).get("/api/inventory/warehouses/").status_code, 200)
        self.assertEqual(self._client(self.cashier).get("/api/inventory/warehouses/").status_code, 403)

    def test_stocks_cashier_can_read(self):
        self.assertEqual(self._client(self.cashier).get("/api/inventory/stocks/").status_code, 200)

    def test_receipts_manager_ok_cashier_forbidden(self):
        payload = {
            "warehouse": self.wh1.id,
            "items": [{"variant": self.variant.id, "quantity": "2", "purchase_price": "40"}],
        }
        self.assertEqual(
            self._client(self.manager).post("/api/inventory/receipts/", payload, format="json").status_code,
            201,
        )
        self.assertEqual(
            self._client(self.cashier).post("/api/inventory/receipts/", payload, format="json").status_code,
            403,
        )
        self.assertEqual(self._client(self.cashier).get("/api/inventory/receipts/").status_code, 403)

    # --- Касса --------------------------------------------------------------
    def test_registers_cashier_sees_only_own_branch(self):
        resp = self._client(self.cashier).get("/api/sales/registers/")
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in resp.json()["results"]}
        self.assertIn(self.register1.id, ids)
        self.assertNotIn(self.register2.id, ids)

    def test_cashier_can_open_shift_own_branch(self):
        resp = self._client(self.cashier).post(
            "/api/sales/shifts/open/", {"register": self.register1.id, "opening_cash": 0}, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_cashier_cannot_open_shift_other_branch(self):
        resp = self._client(self.cashier).post(
            "/api/sales/shifts/open/", {"register": self.register2.id, "opening_cash": 0}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_cashier_full_sale_flow(self):
        client = self._client(self.cashier)
        opened = client.post(
            "/api/sales/shifts/open/", {"register": self.register1.id, "opening_cash": 0}, format="json"
        )
        self.assertEqual(opened.status_code, 201, opened.content)
        shift_id = opened.json()["id"]
        sale = client.post(
            "/api/sales/sales/",
            {
                "shift": shift_id,
                "payment_type": "cash",
                "paid_cash": 100,
                "items": [{"variant": self.variant.id, "quantity": 1, "price": 100}],
            },
            format="json",
        )
        self.assertEqual(sale.status_code, 201, sale.content)

    # --- Нет членства -------------------------------------------------------
    def test_no_membership_forbidden(self):
        client = self._client(self.nomember)
        self.assertEqual(client.get("/api/catalog/products/").status_code, 403)
        self.assertEqual(client.get("/api/sales/registers/").status_code, 403)
        self.assertEqual(
            client.post(
                "/api/sales/shifts/open/", {"register": self.register1.id}, format="json"
            ).status_code,
            403,
        )
