from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "sku", "unit_price", "quantity", "line_total"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source="cashier.username", read_only=True)
    refunded_by_name = serializers.CharField(source="refunded_by.username", read_only=True, default=None)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "number",
            "status",
            "cashier",
            "cashier_name",
            "total",
            "payment_method",
            "cash_received",
            "change_due",
            "created_at",
            "refunded_at",
            "refunded_by_name",
            "item_count",
            "items",
        ]

    def get_item_count(self, obj):
        return sum(item.quantity for item in obj.items.all())


class SaleItemInputSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class SaleInputSerializer(serializers.Serializer):
    items = SaleItemInputSerializer(many=True, allow_empty=False)
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)
    cash_received = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )
