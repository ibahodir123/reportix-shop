from decimal import Decimal

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.catalog.models import Product
from apps.inventory.models import Stock, StockMovement, Warehouse
from apps.tenants.models import Branch, Membership, Tenant, User

from .engine import handle_message

URL = "/api/assistant/message/"


class AssistantBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="owner", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        self.membership = Membership.objects.create(
            tenant=self.tenant, user=self.user, role=Membership.ROLE_OWNER
        )
        self.branch = Branch.objects.create(tenant=self.tenant, name="Центр")
        self.warehouse = Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Основной"
        )
        self.client = APIClient()
        self.client.force_login(self.user)

    def say(self, text, conversation_id=None):
        payload = {"text": text}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        resp = self.client.post(URL, payload, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()


class AssistantHappyPathTests(AssistantBase):
    PHRASE = "Прими футболку синяя размер эль закуп 45 тысяч продажа 79 тысяч 20 штук"

    def test_intake_dialog_creates_product_and_stock(self):
        step1 = self.say(self.PHRASE)
        self.assertEqual(step1["state"], "collecting")
        self.assertIn("склад", step1["reply"].lower())
        cid = step1["conversation_id"]

        step2 = self.say("Да", cid)
        self.assertEqual(step2["state"], "confirm")
        self.assertIsNotNone(step2["draft"])
        self.assertEqual(step2["draft"]["product"]["quantity"], "20")

        step3 = self.say("Подтверждаю", cid)
        self.assertEqual(step3["state"], "done")
        self.assertIsNotNone(step3["result"])

        product = Product.objects.get(tenant=self.tenant)
        variant = product.variants.get()
        self.assertEqual(variant.purchase_price, Decimal("45000.00"))
        self.assertEqual(variant.sale_price, Decimal("79000.00"))
        stock = Stock.objects.get(warehouse=self.warehouse, variant=variant)
        self.assertEqual(stock.quantity, Decimal("20.000"))
        self.assertTrue(
            StockMovement.objects.filter(
                variant=variant, movement_type=StockMovement.TYPE_IN
            ).exists()
        )

    def test_warehouse_named_in_first_message_skips_proposal(self):
        step1 = self.say(self.PHRASE + " на основной склад")
        self.assertEqual(step1["state"], "confirm")
        self.say("Подтверждаю", step1["conversation_id"])
        self.assertEqual(Product.objects.filter(tenant=self.tenant).count(), 1)

    def test_double_confirm_creates_single_product(self):
        cid = self.say(self.PHRASE)["conversation_id"]
        self.say("Да", cid)
        self.say("Подтверждаю", cid)
        # Повторное «Подтверждаю» на завершённом диалоге — не создаёт дубль.
        again = self.say("Подтверждаю", cid)
        self.assertNotEqual(again["state"], "done")
        self.assertEqual(Product.objects.filter(tenant=self.tenant).count(), 1)


class AssistantCollectingTests(AssistantBase):
    def test_asks_for_missing_quantity_then_price(self):
        step1 = self.say("Создай товар ручка")
        self.assertEqual(step1["state"], "collecting")
        self.assertIn("штук", step1["reply"].lower())
        cid = step1["conversation_id"]

        step2 = self.say("20", cid)
        self.assertIn("цен", step2["reply"].lower())

        step3 = self.say("5 тысяч", cid)
        # Дальше — предложение склада.
        self.assertIn("склад", step3["reply"].lower())

    def test_cancel_at_confirm(self):
        cid = self.say(AssistantHappyPathTests.PHRASE)["conversation_id"]
        self.say("Да", cid)
        out = self.say("Отмена", cid)
        self.assertEqual(out["state"], "cancelled")
        self.assertEqual(Product.objects.filter(tenant=self.tenant).count(), 0)

    def test_decline_warehouse_then_pick_another(self):
        Warehouse.objects.create(
            tenant=self.tenant, branch=self.branch, name="Второй"
        )
        cid = self.say(AssistantHappyPathTests.PHRASE)["conversation_id"]
        out = self.say("Нет", cid)
        self.assertEqual(out["state"], "collecting")
        self.assertIn("какой склад", out["reply"].lower())
        pick = self.say("Второй", cid)
        self.assertEqual(pick["state"], "confirm")

    def test_unknown_message_returns_help(self):
        out = self.say("привет как дела")
        self.assertIn("прими", out["reply"].lower())
        self.assertEqual(Product.objects.filter(tenant=self.tenant).count(), 0)

    @override_settings(STT_PROVIDER="mock")
    def test_audio_is_transcribed_and_starts_intake(self):
        # Форсируем mock-STT, чтобы тест не зависел от настройки сервера
        # (в проде STT_PROVIDER может быть "google" с реальным ffmpeg).
        audio = SimpleUploadedFile("a.webm", b"0000", content_type="audio/webm")
        resp = self.client.post(URL, {"audio": audio}, format="multipart")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["state"], "collecting")


class AssistantPermissionTests(AssistantBase):
    def test_requires_tenant(self):
        other = User.objects.create_user(username="notenant", password="pass12345")
        client = APIClient()
        client.force_login(other)
        resp = client.post(URL, {"text": "Прими товар"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_cashier_forbidden_at_endpoint(self):
        cashier = User.objects.create_user(username="cashier", password="pass12345")
        Membership.objects.create(
            tenant=self.tenant,
            user=cashier,
            role=Membership.ROLE_CASHIER,
            branch=self.branch,
        )
        client = APIClient()
        client.force_login(cashier)
        resp = client.post(URL, {"text": "Прими товар"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_engine_execute_rechecks_role(self):
        # Защита в глубину: даже если дойти до выполнения с ролью кассира,
        # движок откажет (endpoint кассира и так не пускает).
        cashier = User.objects.create_user(username="c2", password="pass12345")
        membership = Membership.objects.create(
            tenant=self.tenant,
            user=cashier,
            role=Membership.ROLE_CASHIER,
            branch=self.branch,
        )
        phrase = AssistantHappyPathTests.PHRASE
        start = handle_message(
            tenant=self.tenant, user=cashier, membership=membership,
            conversation_id=None, text=phrase,
        )
        cid = start["conversation_id"]
        handle_message(
            tenant=self.tenant, user=cashier, membership=membership,
            conversation_id=cid, text="Да",
        )
        out = handle_message(
            tenant=self.tenant, user=cashier, membership=membership,
            conversation_id=cid, text="Подтверждаю",
        )
        self.assertEqual(out["state"], "cancelled")
        self.assertIn("прав", out["reply"].lower())
        self.assertEqual(Product.objects.filter(tenant=self.tenant).count(), 0)
