from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.catalog.models import Variant
from apps.common.api import TenantScopedViewSet
from apps.common.permissions import CASHIER, PosAccess, RegistersAccess

from .models import CashierShift, CashRegister, Sale
from .serializers import (
    CashierShiftSerializer,
    CashRegisterSerializer,
    CloseShiftSerializer,
    OpenShiftSerializer,
    SaleCreateSerializer,
    SaleSerializer,
)
from .services import build_z_report, close_shift, create_sale, open_shift


def _require_tenant(request):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise PermissionDenied("Не выбран тенант (бизнес-аккаунт).")
    return tenant


def _cashier_branch(request):
    """Филиал кассира, если он ограничен филиалом; иначе None."""
    membership = getattr(request, "membership", None)
    if membership is not None and membership.role == CASHIER and membership.branch_id:
        return membership.branch_id
    return None


class CashRegisterViewSet(TenantScopedViewSet):
    queryset = CashRegister.objects.select_related("branch", "warehouse")
    serializer_class = CashRegisterSerializer
    permission_classes = [RegistersAccess]

    def get_queryset(self):
        qs = super().get_queryset()
        # Кассир с привязкой к филиалу видит только кассы своего филиала.
        branch_id = _cashier_branch(self.request)
        if branch_id is not None:
            qs = qs.filter(branch_id=branch_id)
        return qs


class CashierShiftViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Смены. Открытие — POST /shifts/open/, закрытие — POST /shifts/{id}/close/."""

    queryset = CashierShift.objects.select_related("register", "cashier")
    serializer_class = CashierShiftSerializer
    permission_classes = [PosAccess]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(tenant=tenant)

    @action(detail=False, methods=["get"])
    def current(self, request):
        """Текущая открытая смена кассира (если есть)."""
        tenant = _require_tenant(request)
        shift = (
            self.get_queryset()
            .filter(cashier=request.user, status=CashierShift.STATUS_OPEN)
            .first()
        )
        if shift is None:
            return Response({"detail": "Нет открытой смены."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CashierShiftSerializer(shift).data)

    @action(detail=False, methods=["post"])
    def open(self, request):
        tenant = _require_tenant(request)
        serializer = OpenShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        register = serializer.validated_data["register"]
        if register.tenant_id != tenant.id:
            raise ValidationError("Касса принадлежит другому бизнесу.")
        # Кассир с привязкой к филиалу может открывать смену только на кассе
        # своего филиала.
        branch_id = _cashier_branch(request)
        if branch_id is not None and register.branch_id != branch_id:
            raise PermissionDenied("Касса другого филиала недоступна.")
        shift = open_shift(
            tenant=tenant,
            register=register,
            cashier=request.user,
            opening_cash=serializer.validated_data["opening_cash"],
        )
        return Response(CashierShiftSerializer(shift).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        shift = self.get_object()
        serializer = CloseShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = close_shift(shift=shift, closing_cash=serializer.validated_data.get("closing_cash"))
        return Response(build_z_report(shift))

    @action(detail=True, methods=["get"])
    def z_report(self, request, pk=None):
        return Response(build_z_report(self.get_object()))


class SaleViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Продажи. Создание — POST /sales/ с nested items."""

    queryset = Sale.objects.select_related("shift", "warehouse").prefetch_related("items__variant")
    serializer_class = SaleSerializer
    permission_classes = [PosAccess]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return self.queryset.none()
        return self.queryset.filter(tenant=tenant)

    def create(self, request, *args, **kwargs):
        tenant = _require_tenant(request)
        payload = SaleCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        shift = (
            CashierShift.objects.filter(tenant=tenant, pk=data["shift"])
            .select_related("register__warehouse", "register__branch")
            .first()
        )
        if shift is None:
            raise NotFound("Смена не найдена.")

        variant_ids = [row["variant"] for row in data["items"]]
        variants = {
            v.id: v for v in Variant.objects.filter(tenant=tenant, id__in=variant_ids)
        }
        items = []
        for row in data["items"]:
            variant = variants.get(row["variant"])
            if variant is None:
                raise ValidationError(f"Вариант {row['variant']} не найден.")
            items.append(
                {
                    "variant": variant,
                    "quantity": row["quantity"],
                    "price": row["price"],
                    "discount": row.get("discount", 0),
                }
            )

        sale = create_sale(
            tenant=tenant,
            shift=shift,
            cashier=request.user,
            items=items,
            discount=data["discount"],
            payment_type=data["payment_type"],
            paid_cash=data["paid_cash"],
            paid_card=data["paid_card"],
            client_uuid=data.get("client_uuid"),
        )
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)
