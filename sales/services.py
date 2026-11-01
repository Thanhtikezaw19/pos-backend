from collections import OrderedDict
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from catalog.models import Product

from .models import Order, OrderItem


@transaction.atomic
def create_sale(*, cashier, items, payment_method, cash_received=None):
    """Create a completed order and deduct stock.

    `items` is a list of {"product": id, "quantity": int}. Duplicate products are merged.
    Product rows are locked so concurrent sales can't oversell.
    """
    quantities = OrderedDict()
    for item in items:
        quantities[item["product"]] = quantities.get(item["product"], 0) + item["quantity"]

    products = {
        p.id: p
        for p in Product.objects.select_for_update().filter(id__in=quantities.keys(), is_active=True)
    }
    missing = [pid for pid in quantities if pid not in products]
    if missing:
        raise ValidationError({"items": f"Products not found or inactive: {missing}"})

    short = [
        f"{products[pid].name} (in stock: {products[pid].stock}, requested: {qty})"
        for pid, qty in quantities.items()
        if products[pid].stock < qty
    ]
    if short:
        raise ValidationError({"items": ["Not enough stock: " + ", ".join(short)]})

    total = sum((products[pid].price * qty for pid, qty in quantities.items()), Decimal("0"))

    change_due = Decimal("0")
    if payment_method == Order.PaymentMethod.CASH:
        if cash_received is None:
            raise ValidationError({"cash_received": "Cash received is required for cash payments."})
        if cash_received < total:
            raise ValidationError({"cash_received": "Cash received is less than the total."})
        change_due = cash_received - total
    else:
        cash_received = None

    order = Order.objects.create(
        number=f"TMP-{uuid4().hex[:28]}",
        cashier=cashier,
        total=total,
        payment_method=payment_method,
        cash_received=cash_received,
        change_due=change_due,
    )
    order.number = f"{timezone.localdate():%Y%m%d}-{order.pk:06d}"
    order.save(update_fields=["number"])

    order_items = []
    for pid, qty in quantities.items():
        product = products[pid]
        order_items.append(
            OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                unit_price=product.price,
                quantity=qty,
                line_total=product.price * qty,
            )
        )
        product.stock -= qty
        product.save(update_fields=["stock", "updated_at"])
    OrderItem.objects.bulk_create(order_items)
    return order


@transaction.atomic
def refund_order(*, order_id, user):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.Status.REFUNDED:
        raise ValidationError({"detail": "This order has already been refunded."})

    items = list(order.items.all())
    products = {
        p.id: p for p in Product.objects.select_for_update().filter(id__in=[i.product_id for i in items])
    }
    for item in items:
        product = products[item.product_id]
        product.stock += item.quantity
        product.save(update_fields=["stock", "updated_at"])

    order.status = Order.Status.REFUNDED
    order.refunded_at = timezone.now()
    order.refunded_by = user
    order.save(update_fields=["status", "refunded_at", "refunded_by"])
    return order
