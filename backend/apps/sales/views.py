from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.catalog.models import Variant
from apps.common.api import TenantScopedViewSet
from apps.common.permissions import CASHIER, PosAccess, RegistersAccess

from .models import CashierShift, CashRegister, Return, Sale, SaleItem
from .serializers import (
    CashierShiftSerializer,
    CashRegisterSerializer,
    CloseShiftSerializer,
    OpenShiftSerializer,
    ReturnCreateSerializer,
    ReturnSerializer,
    SaleCreateSerializer,
    SaleReturnableSerializer,
    SaleSerializer,
)
from .services import build_z_report, close_shift, create_return, create_sale, open_shift


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


def _is_cashier(request):
    membership = getattr(request, "membership", None)
    return membership is not None and membership.role == CASHIER


def _forbid_foreign_shift(request, shift):
    """Кассир может работать (закрытие, Z-отчёт, чек) только со своей сменой."""
    if _is_cashier(request) and shift.cashier_id != request.user.id:
        raise PermissionDenied("Доступна только собственная смена.")


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
        qs = self.queryset.filter(tenant=tenant)
        # Кассир видит только свои смены и смены назначенного филиала;
        # owner/manager — все смены тенанта.
        if _is_cashier(self.request):
            own = Q(cashier=self.request.user)
            branch_id = _cashier_branch(self.request)
            if branch_id is not None:
                own |= Q(register__branch_id=branch_id)
            qs = qs.filter(own)
        return qs

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
        _forbid_foreign_shift(request, shift)
        serializer = CloseShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = close_shift(shift=shift, closing_cash=serializer.validated_data.get("closing_cash"))
        return Response(build_z_report(shift))

    @action(detail=True, methods=["get"])
    def z_report(self, request, pk=None):
        shift = self.get_object()
        _forbid_foreign_shift(request, shift)
        return Response(build_z_report(shift))


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
        qs = self.queryset.filter(tenant=tenant)
        # Кассир видит только свои продажи; owner/manager — все.
        if _is_cashier(self.request):
            qs = qs.filter(cashier=self.request.user)
        return qs

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

        # Кассир проводит чек только по СВОЕЙ смене и только в своём филиале.
        if _is_cashier(request):
            if shift.cashier_id != request.user.id:
                raise PermissionDenied("Продажа возможна только по собственной смене.")
            branch_id = _cashier_branch(request)
            if branch_id is not None and shift.register.branch_id != branch_id:
                raise PermissionDenied("Смена другого филиала недоступна.")

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


def _scope_sale_for_cashier(request, sale):
    """
    Для кассира чек доступен только если это его продажа в его филиале.
    Возвращает True, если доступен; иначе False.
    """
    if not _is_cashier(request):
        return True
    if sale.cashier_id != request.user.id:
        return False
    branch_id = _cashier_branch(request)
    return branch_id is None or sale.branch_id == branch_id


class ReturnViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    Возвраты по чеку. История read-only; создание — через атомарное проведение.
    Кассир: только по своим продажам/своей открытой смене/своему филиалу.
    """

    queryset = Return.objects.select_related("sale", "warehouse", "shift").prefetch_related(
        "items__variant"
    )
    serializer_class = ReturnSerializer
    permission_classes = [PosAccess]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return self.queryset.none()
        qs = self.queryset.filter(tenant=tenant)
        if _is_cashier(self.request):
            qs = qs.filter(created_by=self.request.user)
        return qs

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        """Поиск чека по номеру + возвращаемые остатки позиций."""
        tenant = _require_tenant(request)
        raw = request.query_params.get("number")
        try:
            number = int(raw)
        except (TypeError, ValueError):
            raise ValidationError("Укажите корректный номер чека.")
        sale = (
            Sale.objects.filter(tenant=tenant, number=number)
            .select_related("branch", "cashier")
            .prefetch_related("items__variant")
            .first()
        )
        if sale is None or not _scope_sale_for_cashier(request, sale):
            raise NotFound("Чек не найден.")
        return Response(SaleReturnableSerializer(sale).data)

    def create(self, request, *args, **kwargs):
        tenant = _require_tenant(request)
        payload = ReturnCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        client_uuid = data.get("client_uuid")
        if client_uuid:
            existing = Return.objects.filter(tenant=tenant, client_uuid=client_uuid).first()
            if existing is not None:
                return Response(ReturnSerializer(existing).data, status=status.HTTP_200_OK)

        sale = (
            Sale.objects.filter(tenant=tenant, pk=data["sale"])
            .select_related("branch", "warehouse", "cashier")
            .first()
        )
        if sale is None:
            raise NotFound("Чек не найден.")

        shift = None
        if _is_cashier(request):
            # Кассир: только своя продажа, свой филиал, своя открытая смена.
            if sale.cashier_id != request.user.id:
                raise PermissionDenied("Возврат возможен только по собственной продаже.")
            branch_id = _cashier_branch(request)
            if branch_id is not None and sale.branch_id != branch_id:
                raise PermissionDenied("Чек другого филиала недоступен.")
            shift = (
                CashierShift.objects.filter(
                    tenant=tenant,
                    pk=data.get("shift"),
                    cashier=request.user,
                    status=CashierShift.STATUS_OPEN,
                )
                .select_related("register__branch")
                .first()
            )
            if shift is None:
                raise PermissionDenied("Нужна собственная открытая смена.")
            if branch_id is not None and shift.register.branch_id != branch_id:
                raise PermissionDenied("Смена другого филиала недоступна.")
        elif data.get("shift"):
            shift = CashierShift.objects.filter(tenant=tenant, pk=data["shift"]).first()

        item_ids = [row["sale_item"] for row in data["items"]]
        sale_items = {
            si.id: si
            for si in SaleItem.objects.filter(sale=sale, id__in=item_ids).select_related("variant")
        }
        items = []
        for row in data["items"]:
            sale_item = sale_items.get(row["sale_item"])
            if sale_item is None:
                raise ValidationError(f"Позиция {row['sale_item']} не найдена в чеке.")
            items.append({"sale_item": sale_item, "quantity": row["quantity"]})

        document = create_return(
            tenant=tenant,
            sale=sale,
            created_by=request.user,
            shift=shift,
            items=items,
            payment_type=data["payment_type"],
            refund_cash=data["refund_cash"],
            refund_card=data["refund_card"],
            client_uuid=client_uuid,
        )
        return Response(ReturnSerializer(document).data, status=status.HTTP_201_CREATED)
