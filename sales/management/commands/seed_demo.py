from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from catalog.models import Category, Product
from sales.models import Order
from sales.services import create_sale

USERS = [
    ("admin", "admin12345", User.Role.ADMIN),
    ("cashier", "cashier12345", User.Role.CASHIER),
]

PRODUCTS = {
    "Drinks": [
        ("Green Tea", "DR-001", "1500", 40),
        ("Black Coffee", "DR-002", "2500", 30),
        ("Milk Tea", "DR-003", "2000", 35),
        ("Orange Juice", "DR-004", "3000", 20),
        ("Mineral Water", "DR-005", "500", 100),
        ("Cola", "DR-006", "1200", 4),
    ],
    "Bakery": [
        ("Butter Croissant", "BK-001", "2200", 15),
        ("Chocolate Cake Slice", "BK-002", "3500", 8),
        ("Banana Bread", "BK-003", "2800", 3),
        ("Cheese Bun", "BK-004", "1800", 25),
    ],
    "Snacks": [
        ("Potato Chips", "SN-001", "1000", 50),
        ("Peanuts", "SN-002", "800", 60),
        ("Cookies Pack", "SN-003", "1500", 2),
        ("Chocolate Bar", "SN-004", "1300", 45),
        ("Dried Mango", "SN-005", "2500", 18),
    ],
    "Household": [
        ("Tissue Box", "HH-001", "1800", 30),
        ("Dish Soap", "HH-002", "2600", 12),
        ("Laundry Powder 1kg", "HH-003", "5500", 10),
        ("Toothpaste", "HH-004", "2400", 22),
        ("Shampoo", "HH-005", "4800", 5),
    ],
}

SAMPLE_SALES = [
    ([("DR-001", 2), ("BK-001", 1)], "cash", "10000"),
    ([("DR-002", 1), ("SN-004", 3)], "card", None),
    ([("DR-005", 6), ("SN-001", 2), ("SN-002", 1)], "cash", "6000"),
    ([("HH-003", 1), ("HH-001", 2)], "other", None),
    ([("DR-003", 2), ("BK-004", 2)], "cash", "8000"),
]


class Command(BaseCommand):
    help = "Load demo users, products and a few orders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete existing orders and products before loading."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Order.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
        elif Product.objects.exists():
            self.stdout.write(self.style.WARNING("Products already exist. Use --reset to reload."))
            return

        for username, password, role in USERS:
            user, _ = User.objects.get_or_create(username=username, defaults={"role": role})
            user.role = role
            user.is_staff = role == User.Role.ADMIN
            user.is_superuser = role == User.Role.ADMIN
            user.set_password(password)
            user.save()

        for category_name, items in PRODUCTS.items():
            category = Category.objects.create(name=category_name)
            for name, sku, price, stock in items:
                Product.objects.create(name=name, sku=sku, category=category, price=Decimal(price), stock=stock)

        cashier = User.objects.get(username="cashier")
        ids = dict(Product.objects.values_list("sku", "id"))
        for lines, method, cash in SAMPLE_SALES:
            create_sale(
                cashier=cashier,
                items=[{"product": ids[sku], "quantity": qty} for sku, qty in lines],
                payment_method=method,
                cash_received=Decimal(cash) if cash else None,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {Product.objects.count()} products and {Order.objects.count()} orders.\n"
                "Logins: admin / admin12345, cashier / cashier12345"
            )
        )
