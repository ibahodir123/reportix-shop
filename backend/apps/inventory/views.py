from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.api import TenantScopedViewSet

from .models import Stock, StockMovement, Warehouse
from .serializers import StockMovementSerializer, StockSerializer, WarehouseSerializer
from .services import record_movement


class WarehouseViewSet(TenantScopedViewSet):
    queryset = Warehouse.objects.select_related("branch")
    serializer_class = WarehouseSerializer


class StockViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Остатки — только чтение (меняются через движения)."""

    queryset = Stock.objects.select_related("warehouse", "variant__product")
    serializer_class = StockSerializer

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(warehouse__tenant=tenant)


class StockMovementViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Движения товара. Создание идёт через сервис record_movement(), который
    атомарно пересчитывает остаток. Движения неизменяемы (нет update/delete).
    """

    queryset = StockMovement.objects.select_related("warehouse", "variant")
    serializer_class = StockMovementSerializer

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Не выбран тенант (бизнес-аккаунт).")

        data = serializer.validated_data
        warehouse = data["warehouse"]
        variant = data["variant"]
        if warehouse.tenant_id != tenant.id or variant.tenant_id != tenant.id:
            raise ValidationError("Склад или вариант принадлежат другому бизнесу.")

        movement = record_movement(
            tenant=tenant,
            warehouse=warehouse,
            variant=variant,
            movement_type=data["movement_type"],
            quantity=data["quantity"],
            unit_cost=data.get("unit_cost") or 0,
            reference=data.get("reference", ""),
        )
        serializer.instance = movement
