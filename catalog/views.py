from django.db.models import Q
from rest_framework import viewsets

from accounts.permissions import IsPosAdminOrReadOnly

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsPosAdminOrReadOnly]
    pagination_class = None


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsPosAdminOrReadOnly]
    # Products referenced by orders can't be deleted; deactivate them instead.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        qs = Product.objects.select_related("category")
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
        category = params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        active = params.get("active")
        if active in ("true", "false"):
            qs = qs.filter(is_active=active == "true")
        return qs
