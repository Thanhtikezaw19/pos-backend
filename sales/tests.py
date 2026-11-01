from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Product

from .models import Order


class SaleTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("boss", password="x", role=User.Role.ADMIN)
        self.cashier = User.objects.create_user("cash1", password="x", role=User.Role.CASHIER)
        self.other_cashier = User.objects.create_user("cash2", password="x", role=User.Role.CASHIER)
        self.tea = Product.objects.create(name="Green Tea", sku="DR-001", price="1500.00", stock=10)
        self.cake = Product.objects.create(name="Cake", sku="BK-001", price="3250.50", stock=2)

    def sell(self, user, items, payment_method="cash", cash_received="100000"):
        self.client.force_authenticate(user)
        payload = {"items": items, "payment_method": payment_method}
        if cash_received is not None:
            payload["cash_received"] = cash_received
        return self.client.post("/api/orders/", payload, format="json")


class CreateSaleTests(SaleTestBase):
    def test_sale_deducts_stock_and_computes_totals(self):
        res = self.sell(
            self.cashier,
            [{"product": self.tea.id, "quantity": 3}, {"product": self.cake.id, "quantity": 1}],
            cash_received="10000",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["total"], "7750.50")
        self.assertEqual(res.data["change_due"], "2249.50")
        self.assertEqual(len(res.data["items"]), 2)
        self.assertRegex(res.data["number"], r"^\d{8}-\d{6}$")
        self.tea.refresh_from_db()
        self.cake.refresh_from_db()
        self.assertEqual(self.tea.stock, 7)
        self.assertEqual(self.cake.stock, 1)

    def test_duplicate_lines_are_merged(self):
        res = self.sell(
            self.cashier,
            [{"product": self.tea.id, "quantity": 1}, {"product": self.tea.id, "quantity": 2}],
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["items"][0]["quantity"], 3)

    def test_insufficient_stock_rejects_whole_sale(self):
        res = self.sell(
            self.cashier,
            [{"product": self.tea.id, "quantity": 1}, {"product": self.cake.id, "quantity": 3}],
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Not enough stock", str(res.data))
        self.tea.refresh_from_db()
        self.cake.refresh_from_db()
        self.assertEqual(self.tea.stock, 10)
        self.assertEqual(self.cake.stock, 2)
        self.assertEqual(Order.objects.count(), 0)

    def test_inactive_product_rejected(self):
        self.tea.is_active = False
        self.tea.save()
        res = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}])
        self.assertEqual(res.status_code, 400)

    def test_cash_payment_requires_enough_cash(self):
        res = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}], cash_received="1000")
        self.assertEqual(res.status_code, 400)
        res = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}], cash_received=None)
        self.assertEqual(res.status_code, 400)

    def test_card_payment_ignores_cash(self):
        res = self.sell(
            self.cashier, [{"product": self.tea.id, "quantity": 1}], payment_method="card", cash_received=None
        )
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(res.data["cash_received"])
        self.assertEqual(res.data["change_due"], "0.00")

    def test_empty_cart_rejected(self):
        self.assertEqual(self.sell(self.cashier, []).status_code, 400)

    def test_snapshot_survives_price_change(self):
        res = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}])
        self.tea.price = Decimal("9999")
        self.tea.name = "Renamed"
        self.tea.save()
        order = self.client.get(f"/api/orders/{res.data['id']}/").data
        self.assertEqual(order["items"][0]["unit_price"], "1500.00")
        self.assertEqual(order["items"][0]["product_name"], "Green Tea")


class OrderVisibilityTests(SaleTestBase):
    def test_cashier_sees_only_own_orders(self):
        self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}])
        other = self.sell(self.other_cashier, [{"product": self.tea.id, "quantity": 1}])
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.get("/api/orders/").data["count"], 1)
        self.assertEqual(self.client.get(f"/api/orders/{other.data['id']}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/orders/").data["count"], 2)

    def test_date_filter(self):
        old = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}])
        Order.objects.filter(pk=old.data["id"]).update(created_at=timezone.now() - timedelta(days=3))
        self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}])
        self.client.force_authenticate(self.admin)
        today = timezone.localdate().isoformat()
        self.assertEqual(self.client.get(f"/api/orders/?date_from={today}").data["count"], 1)
        self.assertEqual(self.client.get(f"/api/orders/?date_to={today}").data["count"], 2)
        self.assertEqual(self.client.get("/api/orders/?date_from=bad").status_code, 400)


class RefundTests(SaleTestBase):
    def test_admin_refund_restores_stock(self):
        res = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 4}])
        self.client.force_authenticate(self.admin)
        refund = self.client.post(f"/api/orders/{res.data['id']}/refund/")
        self.assertEqual(refund.status_code, 200)
        self.assertEqual(refund.data["status"], "refunded")
        self.assertEqual(refund.data["refunded_by_name"], "boss")
        self.tea.refresh_from_db()
        self.assertEqual(self.tea.stock, 10)

    def test_double_refund_rejected(self):
        res = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 4}])
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/orders/{res.data['id']}/refund/")
        self.assertEqual(self.client.post(f"/api/orders/{res.data['id']}/refund/").status_code, 400)
        self.tea.refresh_from_db()
        self.assertEqual(self.tea.stock, 10)

    def test_cashier_cannot_refund(self):
        res = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}])
        self.assertEqual(self.client.post(f"/api/orders/{res.data['id']}/refund/").status_code, 403)


class DashboardTests(SaleTestBase):
    def test_dashboard_today_figures(self):
        self.sell(self.cashier, [{"product": self.tea.id, "quantity": 2}])
        self.sell(self.cashier, [{"product": self.cake.id, "quantity": 1}])
        refunded = self.sell(self.cashier, [{"product": self.tea.id, "quantity": 1}])
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/orders/{refunded.data['id']}/refund/")

        data = self.client.get("/api/dashboard/").data
        self.assertEqual(data["order_count"], 2)
        self.assertEqual(Decimal(data["sales_total"]), Decimal("6250.50"))
        self.assertEqual(data["top_products"][0]["product_name"], "Green Tea")
        self.assertEqual(data["top_products"][0]["quantity"], 2)
        self.assertEqual([p["sku"] for p in data["low_stock"]], ["BK-001"])

    def test_cashier_cannot_view_dashboard(self):
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 403)
