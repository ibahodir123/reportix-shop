from django.db.models import Q

from apps.common.api import TenantScopedViewSet

from .models import Brand, Category, Product, Unit, Variant
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductSerializer,
    UnitSerializer,
    VariantSerializer,
)


class CategoryViewSet(TenantScopedViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class BrandViewSet(TenantScopedViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


class UnitViewSet(TenantScopedViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer


class ProductViewSet(TenantScopedViewSet):
    queryset = Product.objects.select_related("category", "brand", "unit").prefetch_related(
        "variants__barcodes"
    )
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)
        return qs


class VariantViewSet(TenantScopedViewSet):
    queryset = Variant.objects.select_related("product").prefetch_related("barcodes")
    serializer_class = VariantSerializer

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
