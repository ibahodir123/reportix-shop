from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.inventory.models import Stock, StockMovement, Warehouse
from apps.tenants.models import Branch, Membership, Tenant, User

from .models import Product, Variant


class QuickProductTests(TestCase):
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
        self.client = APIClient()
        self.client.force_login(self.user)

    def test_create_with_stock_intake(self):
        resp = self.client.post(
            "/api/catalog/quick-product/",
            {
                "name": "Футболка",
                "color": "синий",
                "size": "L",
                "purchase_price": "45000",
                "sale_price": "79000",
                "quantity": "20",
                "warehouse": self.warehouse.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        product = Product.objects.get(tenant=self.tenant, name="Футболка")
        variant = product.variants.get()
        self.assertEqual(variant.purchase_price, Decimal("45000.00"))
        self.assertEqual(variant.sale_price, Decimal("79000.00"))
        self.assertEqual(variant.attributes.get("color"), "синий")
        self.assertEqual(variant.attributes.get("size"), "L")

        stock = Stock.objects.get(warehouse=self.warehouse, variant=variant)
        self.assertEqual(stock.quantity, Decimal("20.000"))
        self.assertTrue(
            StockMovement.objects.filter(
                variant=variant, movement_type=StockMovement.TYPE_IN
            ).exists()
        )

    def test_quantity_requires_warehouse(self):
        resp = self.client.post(
            "/api/catalog/quick-product/",
            {"name": "Ручка", "sale_price": "5000", "quantity": "3"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_zero_quantity_creates_no_stock(self):
        resp = self.client.post(
            "/api/catalog/quick-product/",
            {"name": "Кружка", "sale_price": "10000"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        product = Product.objects.get(tenant=self.tenant, name="Кружка")
        self.assertFalse(Stock.objects.filter(variant__product=product).exists())

    def test_requires_tenant(self):
        other = User.objects.create_user(username="notenant", password="pass12345")
        client = APIClient()
        client.force_login(other)
        resp = client.post(
            "/api/catalog/quick-product/", {"name": "X"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_auto_sku_is_unique(self):
        # Два товара без SKU получают разные автогенерированные артикулы.
        for name in ("Товар1", "Товар2"):
            resp = self.client.post(
                "/api/catalog/quick-product/",
                {"name": name, "sale_price": "1000"},
                format="json",
            )
            self.assertEqual(resp.status_code, 201, resp.content)
        skus = list(
            Variant.objects.filter(tenant=self.tenant).values_list("sku", flat=True)
        )
        self.assertEqual(len(skus), len(set(skus)))
