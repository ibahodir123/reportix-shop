from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.tenants.models import Membership, Tenant, User
from core.env_utils import INSECURE_DEFAULT, get_secret_key

PRODUCTS_URL = "/api/catalog/products/"


class SecretKeyTests(SimpleTestCase):
    def test_value_used_in_production(self):
        self.assertEqual(get_secret_key("real-key", debug=False), "real-key")

    def test_debug_allows_default(self):
        self.assertEqual(get_secret_key("", debug=True), INSECURE_DEFAULT)

    def test_missing_in_production_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            get_secret_key("", debug=False)

    def test_insecure_default_in_production_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            get_secret_key(INSECURE_DEFAULT, debug=False)


class TenantHeaderMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pass12345")
        self.tenant = Tenant.objects.create(name="A", owner=self.user)
        Membership.objects.create(
            tenant=self.tenant, user=self.user, role=Membership.ROLE_OWNER
        )
        # Тенант, к которому пользователь НЕ принадлежит.
        self.foreign = Tenant.objects.create(name="B", owner=self.user)
        self.client = APIClient()
        self.client.force_login(self.user)

    def test_no_header_uses_default_membership(self):
        resp = self.client.get(PRODUCTS_URL)
        self.assertEqual(resp.status_code, 200)

    def test_valid_header_ok(self):
        resp = self.client.get(PRODUCTS_URL, HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(resp.status_code, 200)

    def test_non_integer_header_is_403_not_500(self):
        resp = self.client.get(PRODUCTS_URL, HTTP_X_TENANT_ID="abc")
        self.assertEqual(resp.status_code, 403)

    def test_foreign_tenant_header_is_403_no_fallback(self):
        resp = self.client.get(PRODUCTS_URL, HTTP_X_TENANT_ID=str(self.foreign.id))
        self.assertEqual(resp.status_code, 403)

    def test_unknown_tenant_header_is_403(self):
        resp = self.client.get(PRODUCTS_URL, HTTP_X_TENANT_ID="99999999")
        self.assertEqual(resp.status_code, 403)
