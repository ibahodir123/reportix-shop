class TenantContextMiddleware:
    """
    Проставляет request.tenant и request.membership по аутентифицированному
    пользователю. Тенант выбирается заголовком X-Tenant-ID (если пользователь
    состоит в нём), иначе берётся первое членство.

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
            tenant_id = request.headers.get("X-Tenant-ID")
            membership = None
            if tenant_id:
                membership = memberships.filter(tenant_id=tenant_id).first()
            if membership is None:
                membership = memberships.first()
            if membership is not None:
                request.tenant = membership.tenant
                request.membership = membership

        return self.get_response(request)
