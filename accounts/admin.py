from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "first_name", "last_name", "role", "is_active"]
    list_filter = ["role", "is_active"]
    fieldsets = BaseUserAdmin.fieldsets + (("POS", {"fields": ["role"]}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("POS", {"fields": ["role"]}),)
