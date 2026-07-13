import uuid
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Product, Unit, Variant
from apps.tenants.models import Branch, Membership, Tenant, User

from .admin import ReceiptAdmin, ReceiptItemInline, StockAdmin, StockMovementAdmin
from .models import Receipt, ReceiptItem, Stock, StockMovement, Warehouse
from .services import create_receipt, record_movement

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
        self.client.force_login(self.user)

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
        client.force_login(other)
        resp = client.post(
            URL,
            {"warehouse": self.warehouse.id, "items": [{"variant": self.v1.id, "quantity": "1"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_history_api_is_read_only(self):
        created = self.client.post(
            URL,
            {
                "warehouse": self.warehouse.id,
                "items": [{"variant": self.v1.id, "quantity": "2", "purchase_price": "100"}],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        rid = created.json()["id"]
        detail = f"{URL}{rid}/"

        # Изменение и удаление проведённой приёмки через API запрещены.
        self.assertEqual(
            self.client.patch(detail, {"supplier_name": "x"}, format="json").status_code, 405
        )
        self.assertEqual(
            self.client.put(
                detail,
                {"warehouse": self.warehouse.id, "items": []},
                format="json",
            ).status_code,
            405,
        )
        self.assertEqual(self.client.delete(detail).status_code, 405)
        # Чтение по-прежнему доступно, документ на месте.
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(Receipt.objects.count(), 1)


class RecordMovementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Основной"
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.variant = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("10")
        )

    def test_out_below_zero_raises_and_no_movement(self):
        from apps.common.exceptions import InsufficientStock

        record_movement(
            tenant=self.tenant,
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=StockMovement.TYPE_IN,
            quantity=Decimal("3"),
        )
        with self.assertRaises(InsufficientStock):
            record_movement(
                tenant=self.tenant,
                warehouse=self.warehouse,
                variant=self.variant,
                movement_type=StockMovement.TYPE_OUT,
                quantity=Decimal("-5"),
            )
        stock = Stock.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(stock.quantity, Decimal("3.000"))
        self.assertEqual(StockMovement.objects.count(), 1)  # только приход


class ReceiptImmutabilityModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Основной"
        )
        self.warehouse2 = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Второй"
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.variant = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("10")
        )
        self.receipt = create_receipt(
            tenant=self.tenant,
            warehouse=self.warehouse,
            created_by=self.user,
            items=[{"variant": self.variant, "quantity": Decimal("2"), "purchase_price": "100"}],
        )

    def test_cannot_change_warehouse(self):
        r = Receipt.objects.get(pk=self.receipt.pk)
        r.warehouse = self.warehouse2
        with self.assertRaises(ValidationError):
            r.save()

    def test_cannot_change_total_cost(self):
        r = Receipt.objects.get(pk=self.receipt.pk)
        r.total_cost = Decimal("1")
        with self.assertRaises(ValidationError):
            r.save()

    def test_cannot_delete_receipt(self):
        r = Receipt.objects.get(pk=self.receipt.pk)
        with self.assertRaises(ValidationError):
            r.delete()
        self.assertEqual(Receipt.objects.count(), 1)

    def test_cannot_change_item(self):
        item = self.receipt.items.first()
        item.quantity = Decimal("99")
        with self.assertRaises(ValidationError):
            item.save()

    def test_cannot_delete_item(self):
        item = self.receipt.items.first()
        with self.assertRaises(ValidationError):
            item.delete()
        self.assertEqual(ReceiptItem.objects.count(), 1)

    def test_cannot_change_or_delete_movement(self):
        movement = StockMovement.objects.get(reference=f"Приёмка #{self.receipt.pk}")
        movement.quantity = Decimal("99")
        with self.assertRaises(ValidationError):
            movement.save()
        fresh = StockMovement.objects.get(pk=movement.pk)
        with self.assertRaises(ValidationError):
            fresh.delete()


class ReceiptAdminPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Основной"
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.variant = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("10")
        )
        self.receipt = create_receipt(
            tenant=self.tenant,
            warehouse=self.warehouse,
            created_by=self.user,
            items=[{"variant": self.variant, "quantity": Decimal("1"), "purchase_price": "100"}],
        )
        self.req = RequestFactory().get("/")
        self.req.user = self.user

    def test_receipt_admin_no_add_no_delete(self):
        admin = ReceiptAdmin(Receipt, AdminSite())
        self.assertFalse(admin.has_add_permission(self.req))
        self.assertFalse(admin.has_delete_permission(self.req, self.receipt))

    def test_receipt_admin_all_fields_readonly(self):
        admin = ReceiptAdmin(Receipt, AdminSite())
        ro = set(admin.get_readonly_fields(self.req, self.receipt))
        for field in ("tenant", "warehouse", "created_by", "total_cost", "client_uuid"):
            self.assertIn(field, ro)

    def test_inline_no_add_change_delete(self):
        inline = ReceiptItemInline(Receipt, AdminSite())
        self.assertFalse(inline.has_add_permission(self.req, self.receipt))
        self.assertFalse(inline.has_change_permission(self.req, self.receipt))
        self.assertFalse(inline.has_delete_permission(self.req, self.receipt))

    def test_change_permission_false_view_true(self):
        admin = ReceiptAdmin(Receipt, AdminSite())
        self.assertFalse(admin.has_change_permission(self.req, self.receipt))
        self.assertTrue(admin.has_view_permission(self.req, self.receipt))


class ReceiptAdminViewOnlyHtmlTests(TestCase):
    """Рендерим страницу admin и проверяем, что нет submit/удаления."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin", email="a@a.com", password="pass12345"
        )
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.superuser)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Основной"
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.variant = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("10")
        )
        self.receipt = create_receipt(
            tenant=self.tenant,
            warehouse=self.warehouse,
            created_by=self.superuser,
            items=[{"variant": self.variant, "quantity": Decimal("1"), "purchase_price": "100"}],
        )
        self.client.force_login(self.superuser)

    def test_change_page_is_view_only_no_submit_buttons(self):
        url = f"/admin/inventory/receipt/{self.receipt.id}/change/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Нет кнопок «Сохранить» / «…и продолжить» / «…и добавить».
        self.assertNotIn('name="_save"', html)
        self.assertNotIn('name="_continue"', html)
        self.assertNotIn('name="_addanother"', html)
        # Нет ссылки удаления.
        self.assertNotIn(f"/admin/inventory/receipt/{self.receipt.id}/delete/", html)

    def test_changelist_still_works(self):
        resp = self.client.get("/admin/inventory/receipt/")
        self.assertEqual(resp.status_code, 200)


class StockAuditAdminTests(TestCase):
    """StockMovement и Stock в admin — строго только просмотр."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin", email="a@a.com", password="pass12345"
        )
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.superuser)
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Основной"
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name="Штука", short_name="шт")
        product = Product.objects.create(tenant=self.tenant, name="Товар", unit=self.unit)
        self.variant = Variant.objects.create(
            tenant=self.tenant, product=product, sku="A-1", purchase_price=Decimal("10")
        )
        record_movement(
            tenant=self.tenant,
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=StockMovement.TYPE_IN,
            quantity=Decimal("5"),
        )
        self.movement = StockMovement.objects.get(tenant=self.tenant)
        self.stock = Stock.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.req = RequestFactory().get("/")
        self.req.user = self.superuser
        self.client.force_login(self.superuser)

    def _admins(self):
        return (
            StockMovementAdmin(StockMovement, AdminSite()),
            StockAdmin(Stock, AdminSite()),
        )

    def test_view_only_permissions(self):
        for admin in self._admins():
            self.assertFalse(admin.has_add_permission(self.req))
            self.assertFalse(admin.has_change_permission(self.req))
            self.assertFalse(admin.has_delete_permission(self.req))
            self.assertTrue(admin.has_view_permission(self.req))

    def test_get_actions_has_no_delete_selected(self):
        for admin in self._admins():
            self.assertNotIn("delete_selected", admin.get_actions(self.req))

    def test_pages_open_without_save_add(self):
        detail_pages = [
            f"/admin/inventory/stockmovement/{self.movement.id}/change/",
            f"/admin/inventory/stock/{self.stock.id}/change/",
        ]
        for url in detail_pages:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            html = resp.content.decode()
            self.assertNotIn('name="_save"', html)
            self.assertNotIn('name="_continue"', html)
            self.assertNotIn('name="_addanother"', html)

        for url in ("/admin/inventory/stockmovement/", "/admin/inventory/stock/"):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertNotIn("addlink", resp.content.decode())  # нет кнопки «Добавить»

    def test_post_add_change_delete_forbidden(self):
        mv_before = StockMovement.objects.count()
        add = self.client.post("/admin/inventory/stockmovement/add/", {})
        change = self.client.post(
            f"/admin/inventory/stockmovement/{self.movement.id}/change/", {}
        )
        delete = self.client.post(
            f"/admin/inventory/stockmovement/{self.movement.id}/delete/", {"post": "yes"}
        )
        self.assertEqual(add.status_code, 403)
        self.assertEqual(change.status_code, 403)
        self.assertEqual(delete.status_code, 403)
        self.assertEqual(StockMovement.objects.count(), mv_before)
        self.assertEqual(self.movement, StockMovement.objects.get(pk=self.movement.pk))

    def test_bulk_delete_selected_does_not_delete(self):
        mv_before = StockMovement.objects.count()
        st_before = Stock.objects.count()
        self.client.post(
            "/admin/inventory/stockmovement/",
            {"action": "delete_selected", "_selected_action": [str(self.movement.id)]},
        )
        self.client.post(
            "/admin/inventory/stock/",
            {"action": "delete_selected", "_selected_action": [str(self.stock.id)]},
        )
        self.assertEqual(StockMovement.objects.count(), mv_before)
        self.assertEqual(Stock.objects.count(), st_before)
