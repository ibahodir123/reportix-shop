from rest_framework import serializers

from .models import Barcode, Brand, Category, Product, Unit, Variant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent", "created_at"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "created_at"]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "short_name", "allow_fractional"]


class BarcodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barcode
        fields = ["id", "code"]


class VariantSerializer(serializers.ModelSerializer):
    barcodes = BarcodeSerializer(many=True, read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Variant
        fields = [
            "id",
            "product",
            "product_name",
            "sku",
            "name",
            "attributes",
            "purchase_price",
            "sale_price",
            "is_active",
            "barcodes",
        ]

    def validate_product(self, product):
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is not None and product.tenant_id != tenant.id:
            raise serializers.ValidationError("Товар принадлежит другому бизнесу.")
        return product


class ProductSerializer(serializers.ModelSerializer):
    variants = VariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "category",
            "brand",
            "unit",
            "description",
            "is_active",
            "variants",
            "created_at",
        ]


class QuickProductInputSerializer(serializers.Serializer):
    """
    Быстрое создание товара из голосового черновика:
    Product + один Variant (+ опциональный приход количества на склад).
    """

    name = serializers.CharField(max_length=255)
    unit = serializers.IntegerField(required=False, allow_null=True)
    category = serializers.IntegerField(required=False, allow_null=True)
    brand = serializers.IntegerField(required=False, allow_null=True)
    color = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    size = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sku = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    barcode = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    purchase_price = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=0
    )
    sale_price = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=0
    )
    quantity = serializers.DecimalField(
        max_digits=18, decimal_places=3, required=False, default=0
    )
    warehouse = serializers.IntegerField(required=False, allow_null=True)

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Укажите наименование товара.")
        return value
