from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsPosAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_pos_admin)


class IsPosAdminOrReadOnly(BasePermission):
    """Any staff member can read; only POS admins can write."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or request.user.is_pos_admin
