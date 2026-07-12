from rest_framework import serializers

from .models import Receipt, ReceiptItem, Stock, StockMovement, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "branch", "name", "is_active"]


class StockSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source="variant.__str__", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = Stock
        fields = ["id", "warehouse", "warehouse_name", "variant", "variant_name", "quantity"]


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = [
            "id",
            "warehouse",
            "variant",
            "movement_type",
            "quantity",
            "unit_cost",
            "reference",
            "created_at",
        ]
        read_only_fields = ["created_at"]


# --- Приёмка ---------------------------------------------------------------
class ReceiptItemSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source="variant.__str__", read_only=True)

    class Meta:
        model = ReceiptItem
        fields = ["id", "variant", "variant_name", "quantity", "purchase_price", "total"]


class ReceiptSerializer(serializers.ModelSerializer):
    items = ReceiptItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = Receipt
        fields = [
            "id",
            "warehouse",
            "warehouse_name",
            "supplier_name",
            "reference",
            "total_cost",
            "created_at",
            "items",
        ]


class ReceiptItemInputSerializer(serializers.Serializer):
    variant = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    purchase_price = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=0
    )


class ReceiptCreateSerializer(serializers.Serializer):
    warehouse = serializers.IntegerField()
    supplier_name = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    items = ReceiptItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Добавьте хотя бы одну позицию.")
        return value
