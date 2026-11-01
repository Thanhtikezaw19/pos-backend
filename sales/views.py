from datetime import datetime, time, timedelta

from django.db.models import Count, F, Sum
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPosAdmin
from catalog.models import Product
from catalog.serializers import ProductSerializer

from .models import Order, OrderItem
from .serializers import OrderSerializer, SaleInputSerializer
from .services import create_sale, refund_order


def local_day_start(day):
    """Start of a local calendar day as an aware datetime.

    Range filters on created_at avoid __date lookups, which need MySQL's timezone tables.
    """
    return timezone.make_aware(datetime.combine(day, time.min))


def parse_date(value, field):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError({field: "Use the format YYYY-MM-DD."})


class OrderViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.select_related("cashier", "refunded_by").prefetch_related("items")
        user = self.request.user
        if not user.is_pos_admin:
            qs = qs.filter(cashier=user)
        params = self.request.query_params
        if params.get("date_from"):
            qs = qs.filter(created_at__gte=local_day_start(parse_date(params["date_from"], "date_from")))
        if params.get("date_to"):
            end = local_day_start(parse_date(params["date_to"], "date_to")) + timedelta(days=1)
            qs = qs.filter(created_at__lt=end)
        if params.get("status") in Order.Status.values:
            qs = qs.filter(status=params["status"])
        return qs

    def create(self, request, *args, **kwargs):
        data = SaleInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = create_sale(cashier=request.user, **data.validated_data)
        order = self.get_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsPosAdmin])
    def refund(self, request, pk=None):
        order = self.get_object()
        refund_order(order_id=order.pk, user=request.user)
        return Response(OrderSerializer(self.get_queryset().get(pk=order.pk)).data)


class DashboardView(APIView):
    permission_classes = [IsPosAdmin]

    def get(self, request):
        start = local_day_start(timezone.localdate())
        end = start + timedelta(days=1)
        today = Order.objects.filter(
            status=Order.Status.COMPLETED, created_at__gte=start, created_at__lt=end
        )
        totals = today.aggregate(sales_total=Sum("total"), order_count=Count("id"))

        top_products = (
            OrderItem.objects.filter(order__in=today)
            .values("product_id", "product_name")
            .annotate(quantity=Sum("quantity"), revenue=Sum("line_total"))
            .order_by("-quantity", "-revenue")[:5]
        )
        low_stock = Product.objects.filter(is_active=True, stock__lte=F("low_stock_threshold")).select_related(
            "category"
        )

        return Response(
            {
                "date": timezone.localdate(),
                "sales_total": totals["sales_total"] or "0.00",
                "order_count": totals["order_count"],
                "top_products": list(top_products),
                "low_stock": ProductSerializer(low_stock, many=True).data,
            }
        )
