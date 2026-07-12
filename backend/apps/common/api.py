from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied


class TenantScopedViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet, ограниченный текущим тенантом.

    - get_queryset() отдаёт только объекты request.tenant;
    - perform_create() проставляет tenant автоматически.

    Наследники задают queryset и serializer_class как обычно.
    """

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Не выбран тенант (бизнес-аккаунт).")
        serializer.save(tenant=tenant)
