from rest_framework import serializers

from .models import Stock, StockMovement, Warehouse


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
