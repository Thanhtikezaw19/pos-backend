from rest_framework.test import APITestCase

from accounts.models import User

from .models import Category, Product


class ProductApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("boss", password="x", role=User.Role.ADMIN)
        self.cashier = User.objects.create_user("cash1", password="x", role=User.Role.CASHIER)
        self.drinks = Category.objects.create(name="Drinks")
        Product.objects.create(name="Green Tea", sku="DR-001", category=self.drinks, price="1500", stock=10)
        Product.objects.create(name="Coffee", sku="DR-002", category=self.drinks, price="2500", stock=10)
        Product.objects.create(name="Old Snack", sku="SN-001", price="500", stock=0, is_active=False)

    def test_cashier_can_read_but_not_write(self):
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.get("/api/products/").status_code, 200)
        res = self.client.post("/api/products/", {"name": "X", "sku": "X-1", "price": "1"})
        self.assertEqual(res.status_code, 403)

    def test_admin_creates_product(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(
            "/api/products/",
            {"name": "Water", "sku": "DR-003", "category": self.drinks.id, "price": "800.50", "stock": 24},
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["price"], "800.50")
        self.assertEqual(res.data["category_name"], "Drinks")

    def test_search_by_name_or_sku(self):
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.get("/api/products/?search=tea").data["count"], 1)
        self.assertEqual(self.client.get("/api/products/?search=DR-").data["count"], 2)

    def test_filter_active(self):
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.get("/api/products/?active=true").data["count"], 2)
        self.assertEqual(self.client.get("/api/products/?active=false").data["count"], 1)

    def test_products_cannot_be_deleted(self):
        self.client.force_authenticate(self.admin)
        product = Product.objects.first()
        self.assertEqual(self.client.delete(f"/api/products/{product.id}/").status_code, 405)
