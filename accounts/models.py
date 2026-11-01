from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CASHIER = "cashier", "Cashier"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CASHIER)

    @property
    def is_pos_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser
