from rest_framework.test import APITestCase

from .models import User


class AuthTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("boss", password="s3cret-pass", role=User.Role.ADMIN)
        self.cashier = User.objects.create_user("cash1", password="s3cret-pass", role=User.Role.CASHIER)

    def test_login_returns_token_and_user(self):
        res = self.client.post("/api/auth/login/", {"username": "cash1", "password": "s3cret-pass"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.data)
        self.assertEqual(res.data["user"]["role"], "cashier")

    def test_login_wrong_password(self):
        res = self.client.post("/api/auth/login/", {"username": "cash1", "password": "nope"})
        self.assertEqual(res.status_code, 400)

    def test_logout_invalidates_token(self):
        token = self.client.post("/api/auth/login/", {"username": "cash1", "password": "s3cret-pass"}).data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_unauthenticated_requests_rejected(self):
        self.assertEqual(self.client.get("/api/products/").status_code, 401)


class UserManagementTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("boss", password="s3cret-pass", role=User.Role.ADMIN)
        self.cashier = User.objects.create_user("cash1", password="s3cret-pass", role=User.Role.CASHIER)

    def test_cashier_cannot_manage_users(self):
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.get("/api/users/").status_code, 403)

    def test_admin_creates_user_with_hashed_password(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(
            "/api/users/", {"username": "cash2", "password": "an0ther-pass", "role": "cashier"}
        )
        self.assertEqual(res.status_code, 201)
        self.assertNotIn("password", res.data)
        self.assertTrue(User.objects.get(username="cash2").check_password("an0ther-pass"))

    def test_admin_cannot_deactivate_self(self):
        self.client.force_authenticate(self.admin)
        res = self.client.patch(f"/api/users/{self.admin.id}/", {"is_active": False})
        self.assertEqual(res.status_code, 400)
