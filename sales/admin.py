from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "sku", "unit_price", "quantity", "line_total"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["number", "created_at", "cashier", "total", "payment_method", "status"]
    list_filter = ["status", "payment_method"]
    search_fields = ["number"]
    inlines = [OrderItemInline]
    readonly_fields = [f.name for f in Order._meta.fields]
