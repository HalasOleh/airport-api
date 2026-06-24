from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminAllORIsAuthenticatedReadOnly(BasePermission):
    """
    The request is authenticated as an admin - read/write, if as a user - read only request.
    """

    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS and request.user and request.user.is_authenticated
        ) or (d
            request.user and request.user.is_staff
        )#запит може не мати користовача якщо анонімний або none, тому що без цього немає в кого питати і буде помилка