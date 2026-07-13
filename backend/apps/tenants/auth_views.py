"""
Session-аутентификация для SPA.

Поток на фронте:
  1) GET  /api/auth/csrf/   — ставит cookie csrftoken (для последующих POST);
  2) POST /api/auth/login/  — вход по username/password (создаёт сессию);
  3) GET  /api/auth/me/     — кто я (иначе 403 → редирект на вход);
  4) POST /api/auth/logout/ — выход.
"""

from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Membership


def _me_payload(user, active=None):
    memberships = (
        Membership.objects.filter(user=user)
        .select_related("tenant", "branch")
        .order_by("id")
    )
    # Активное членство: выбранный tenant (по X-Tenant-ID) либо первое.
    active_m = active if active is not None else memberships.first()
    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "is_staff": user.is_staff,
        "role": active_m.role if active_m else None,
        "branch": active_m.branch_id if active_m else None,
        "current_tenant": (
            {"id": active_m.tenant_id, "name": active_m.tenant.name} if active_m else None
        ),
        "memberships": [
            {
                "tenant_id": m.tenant_id,
                "tenant_name": m.tenant.name,
                "role": m.role,
                "branch": m.branch_id,
            }
            for m in memberships
        ],
    }


@ensure_csrf_cookie
@require_GET
def csrf(request):
    """Ставит cookie csrftoken. Дёргается фронтом до входа."""
    return JsonResponse({"detail": "CSRF cookie set"})


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"  # rate: settings DEFAULT_THROTTLE_RATES["login"]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        if not username or not password:
            return Response(
                {"detail": "Введите логин и пароль."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Неверный логин или пароль."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {"detail": "Пользователь заблокирован."},
                status=status.HTTP_403_FORBIDDEN,
            )

        django_login(request, user)
        return Response(_me_payload(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        django_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Роль/branch — по активному членству текущего tenant (из middleware).
        return Response(_me_payload(request.user, active=getattr(request, "membership", None)))
