from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.catalog.models import Variant
from apps.common.api import TenantScopedViewSet
from apps.common.permissions import ManageInventory, StockRead

from .models import Receipt, Stock, StockMovement, Warehouse
from .serializers import (
    ReceiptCreateSerializer,
    ReceiptSerializer,
    StockMovementSerializer,
    StockSerializer,
    WarehouseSerializer,
)
from .services import create_receipt, record_movement


class WarehouseViewSet(TenantScopedViewSet):
    queryset = Warehouse.objects.select_related("branch")
    serializer_class = WarehouseSerializer
    permission_classes = [ManageInventory]


class StockViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Остатки — только чтение (меняются через движения)."""

    queryset = Stock.objects.select_related("warehouse", "variant__product")
    serializer_class = StockSerializer
    permission_classes = [StockRead]

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
    permission_classes = [ManageInventory]

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


class ReceiptViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Приёмка товара. Список/детали — история проведённых приёмок.
    Создание (POST) — многострочный документ: атомарно создаёт движения IN
    и обновляет остатки через create_receipt(). Идемпотентно по client_uuid.
    """

    queryset = Receipt.objects.select_related("warehouse").prefetch_related("items__variant")
    serializer_class = ReceiptSerializer
    permission_classes = [ManageInventory]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(tenant=tenant)

    def create(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Не выбран тенант (бизнес-аккаунт).")

        payload = ReceiptCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        client_uuid = data.get("client_uuid")
        # Быстрый путь идемпотентности: повтор возвращает уже проведённый документ.
        if client_uuid:
            existing = Receipt.objects.filter(tenant=tenant, client_uuid=client_uuid).first()
            if existing is not None:
                return Response(ReceiptSerializer(existing).data, status=status.HTTP_200_OK)

        warehouse = Warehouse.objects.filter(tenant=tenant, pk=data["warehouse"]).first()
        if warehouse is None:
            raise NotFound("Склад не найден.")

        variant_ids = [row["variant"] for row in data["items"]]
        variants = {v.id: v for v in Variant.objects.filter(tenant=tenant, id__in=variant_ids)}
        items = []
        for row in data["items"]:
            variant = variants.get(row["variant"])
            if variant is None:
                raise ValidationError(f"Вариант {row['variant']} не найден.")
            items.append(
                {
                    "variant": variant,
                    "quantity": row["quantity"],
                    "purchase_price": row.get("purchase_price") or 0,
                }
            )

        receipt = create_receipt(
            tenant=tenant,
            warehouse=warehouse,
            created_by=request.user,
            items=items,
            supplier_name=data.get("supplier_name", ""),
            reference=data.get("reference", ""),
            client_uuid=client_uuid,
        )
        return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)
