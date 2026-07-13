from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api import TenantScopedViewSet
from apps.common.permissions import ManageCatalog, VariantsAccess

from .models import Brand, Category, Product, Unit, Variant
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductSerializer,
    QuickProductInputSerializer,
    UnitSerializer,
    VariantSerializer,
)
from .services import quick_create_product


class CategoryViewSet(TenantScopedViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [ManageCatalog]


class BrandViewSet(TenantScopedViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [ManageCatalog]


class UnitViewSet(TenantScopedViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [ManageCatalog]


class ProductViewSet(TenantScopedViewSet):
    queryset = Product.objects.select_related("category", "brand", "unit").prefetch_related(
        "variants__barcodes"
    )
    serializer_class = ProductSerializer
    permission_classes = [ManageCatalog]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)
        return qs


class QuickProductCreateView(APIView):
    """
    POST /api/catalog/quick-product/ — быстрое создание товара из голосового
    черновика: Product + Variant (+ опциональный приход количества на склад).
    """

    permission_classes = [ManageCatalog]

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Не выбран тенант (бизнес-аккаунт).")

        serializer = QuickProductInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = quick_create_product(tenant=tenant, data=serializer.validated_data)
        return Response(ProductSerializer(product).data, status=201)


class VariantViewSet(TenantScopedViewSet):
    queryset = Variant.objects.select_related("product").prefetch_related("barcodes")
    serializer_class = VariantSerializer
    permission_classes = [VariantsAccess]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(product__name__icontains=search)
                | Q(sku__icontains=search)
                | Q(barcodes__code=search)
            ).distinct()
        return qs
