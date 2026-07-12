from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.tenants.models import User

from .nlu import parse_product_draft
from .number_words import tokenize, words_to_number
from .providers import MockSTTProvider


def n(s):
    return words_to_number(tokenize(s))


class NumberWordsTests(SimpleTestCase):
    def test_russian(self):
        self.assertEqual(n("сорок пять тысяч"), 45000)
        self.assertEqual(n("сто двадцать"), 120)
        self.assertEqual(n("два миллиона триста"), 2000300)
        self.assertEqual(n("девятьсот девяносто девять"), 999)

    def test_uzbek(self):
        self.assertEqual(n("qirq besh ming"), 45000)
        self.assertEqual(n("ikki yuz ellik"), 250)
        self.assertEqual(n("yetmish to'qqiz ming"), 79000)

    def test_digits(self):
        self.assertEqual(n("45000"), 45000)
        self.assertEqual(n("20"), 20)


class NluTests(SimpleTestCase):
    def test_ru_full_phrase(self):
        d = parse_product_draft(
            "Футболка синяя размер эль закуп 45 тысяч продажа 79 тысяч 20 штук"
        )
        self.assertEqual(d["name"], "Футболка")
        self.assertEqual(d["attributes"].get("color"), "синий")
        self.assertEqual(d["attributes"].get("size"), "L")
        self.assertEqual(d["purchase_price"], "45000")
        self.assertEqual(d["sale_price"], "79000")
        self.assertEqual(d["quantity"], "20")
        self.assertEqual(d["confidence"], "estimated")

    def test_uz_phrase(self):
        d = parse_product_draft(
            "Koylak qizil olish qirq besh ming sotuv yetmish to'qqiz ming yigirma dona"
        )
        self.assertEqual(d["attributes"].get("color"), "красный")
        self.assertEqual(d["purchase_price"], "45000")
        self.assertEqual(d["sale_price"], "79000")
        self.assertEqual(d["quantity"], "20")
        self.assertIsNotNone(d["name"])


class MockProviderTests(SimpleTestCase):
    def test_mock_returns_sample_and_parses(self):
        provider = MockSTTProvider()
        transcript = provider.transcribe(b"")
        d = parse_product_draft(transcript)
        self.assertEqual(d["purchase_price"], "45000")
        self.assertEqual(d["sale_price"], "79000")


class VoiceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_parse_product_from_text(self):
        resp = self.client.post(
            "/api/voice/parse-product/",
            {"text": "Ручка синяя продажа 5 тысяч 100 штук"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["provider"], "text")
        self.assertEqual(body["draft"]["sale_price"], "5000")
        self.assertEqual(body["draft"]["quantity"], "100")

    def test_requires_audio_or_text(self):
        resp = self.client.post("/api/voice/parse-product/", {}, format="json")
        self.assertEqual(resp.status_code, 400)
