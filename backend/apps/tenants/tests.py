from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Membership, Tenant, User


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()  # изолируем счётчик троттлинга между тестами
        self.user = User.objects.create_user(username="cashier", password="pass12345")
        self.tenant = Tenant.objects.create(name="Магазин", owner=self.user)
        Membership.objects.create(
            tenant=self.tenant, user=self.user, role=Membership.ROLE_OWNER
        )
        self.client = APIClient()

    def test_login_success_and_me(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "cashier", "password": "pass12345"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["username"], "cashier")
        self.assertEqual(resp.json()["current_tenant"]["id"], self.tenant.id)

        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "cashier")

    def test_login_wrong_password(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "cashier", "password": "nope"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)

    def test_logout(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)

    def test_login_is_rate_limited(self):
        # rate = 5/min → шестой запрос должен получить 429.
        statuses = []
        for _ in range(6):
            r = self.client.post(
                "/api/auth/login/",
                {"username": "cashier", "password": "wrong"},
                format="json",
            )
            statuses.append(r.status_code)
        self.assertIn(429, statuses)
        self.assertEqual(statuses[-1], 429)
