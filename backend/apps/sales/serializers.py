from rest_framework import serializers

from .models import CashierShift, CashRegister, Sale, SaleItem


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
