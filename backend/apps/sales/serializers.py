from django.db.models import Sum
from rest_framework import serializers

from .models import CashierShift, CashRegister, Return, ReturnItem, Sale, SaleItem


class CashRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashRegister
        fields = ["id", "branch", "warehouse", "name", "is_active"]


class CashierShiftSerializer(serializers.ModelSerializer):
    cashier_name = serializers.CharField(source="cashier.username", read_only=True)

    class Meta:
        model = CashierShift
        fields = [
            "id",
            "register",
            "cashier",
            "cashier_name",
            "status",
            "opened_at",
            "closed_at",
            "opening_cash",
            "closing_cash",
        ]
        read_only_fields = ["cashier", "status", "opened_at", "closed_at", "closing_cash"]


class OpenShiftSerializer(serializers.Serializer):
    register = serializers.PrimaryKeyRelatedField(queryset=CashRegister.objects.all())
    opening_cash = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)


class CloseShiftSerializer(serializers.Serializer):
    closing_cash = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, allow_null=True
    )


class SaleItemSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source="variant.__str__", read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            "id",
            "variant",
            "variant_name",
            "quantity",
            "price",
            "discount",
            "cost_price",
            "total",
        ]
        read_only_fields = ["cost_price", "total"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "number",
            "branch",
            "shift",
            "warehouse",
            "cashier",
            "subtotal",
            "discount",
            "total",
            "payment_type",
            "paid_cash",
            "paid_card",
            "change",
            "status",
            "created_at",
            "items",
        ]


class SaleItemInputSerializer(serializers.Serializer):
    variant = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    price = serializers.DecimalField(max_digits=18, decimal_places=2)
    discount = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)


class SaleCreateSerializer(serializers.Serializer):
    shift = serializers.IntegerField()
    payment_type = serializers.ChoiceField(
        choices=Sale.PAYMENT_CHOICES, default=Sale.PAYMENT_CASH
    )
    discount = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_cash = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_card = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    items = SaleItemInputSerializer(many=True)


# --- Возвраты --------------------------------------------------------------
class ReturnableItemSerializer(serializers.Serializer):
    """Позиция чека с учётом уже возвращённого — для формы возврата."""

    sale_item = serializers.IntegerField(source="id")
    variant = serializers.IntegerField(source="variant_id")
    variant_name = serializers.CharField(source="variant.__str__")
    price = serializers.DecimalField(max_digits=18, decimal_places=2)
    sold = serializers.DecimalField(source="quantity", max_digits=18, decimal_places=3)
    returned = serializers.SerializerMethodField()
    returnable = serializers.SerializerMethodField()

    def _returned(self, obj):
        agg = ReturnItem.objects.filter(sale_item=obj).aggregate(s=Sum("quantity"))
        return agg["s"] or 0

    def get_returned(self, obj):
        return str(self._returned(obj))

    def get_returnable(self, obj):
        return str(obj.quantity - self._returned(obj))


class SaleReturnableSerializer(serializers.ModelSerializer):
    items = ReturnableItemSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = ["id", "number", "created_at", "total", "items"]


class ReturnItemSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source="variant.__str__", read_only=True)

    class Meta:
        model = ReturnItem
        fields = ["id", "sale_item", "variant", "variant_name", "quantity", "price", "total"]


class ReturnSerializer(serializers.ModelSerializer):
    items = ReturnItemSerializer(many=True, read_only=True)

    class Meta:
        model = Return
        fields = [
            "id",
            "sale",
            "branch",
            "warehouse",
            "shift",
            "payment_type",
            "refund_cash",
            "refund_card",
            "refund_total",
            "created_at",
            "items",
        ]


class ReturnItemInputSerializer(serializers.Serializer):
    sale_item = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)


class ReturnCreateSerializer(serializers.Serializer):
    sale = serializers.IntegerField()
    shift = serializers.IntegerField(required=False, allow_null=True)
    payment_type = serializers.ChoiceField(
        choices=Return.PAYMENT_CHOICES, default=Return.PAYMENT_CASH
    )
    refund_cash = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    refund_card = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    client_uuid = serializers.UUIDField(required=False, allow_null=True)
    items = ReturnItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Выберите позиции для возврата.")
        return value
