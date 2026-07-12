from django.http import JsonResponse


class TenantContextMiddleware:
    """
    Проставляет request.tenant и request.membership по аутентифицированному
    пользователю.

    - X-Tenant-ID отсутствует → берётся первое членство (дефолт).
    - X-Tenant-ID задан, но некорректен (не число / не членство пользователя)
      → 403 без fallback на первый tenant и без 500.

    Должен стоять ПОСЛЕ AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        request.membership = None

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            from apps.tenants.models import Membership

            memberships = Membership.objects.filter(user=user).select_related("tenant")
            raw = request.headers.get("X-Tenant-ID")

            if raw:
                try:
                    tenant_id = int(raw)
                except (TypeError, ValueError):
                    return self._forbid(request)
                membership = memberships.filter(tenant_id=tenant_id).first()
                if membership is None:
                    # Некорректный/чужой tenant — никакого fallback.
                    return self._forbid(request)
                request.tenant = membership.tenant
                request.membership = membership
            else:
                membership = memberships.first()
                if membership is not None:
                    request.tenant = membership.tenant
                    request.membership = membership

        return self.get_response(request)

    def _forbid(self, request):
        if request.path.startswith("/api/"):
            return JsonResponse({"detail": "Некорректный X-Tenant-ID."}, status=403)
        # Вне API просто продолжаем с tenant=None (без fallback).
        return self.get_response(request)
