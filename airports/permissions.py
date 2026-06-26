from rest_framework.permissions import BasePermission, SAFE_METHODS

from user.models import User


class IsAdminAllORIsAuthenticatedReadOnly(BasePermission):
    """
    The request is authenticated as an admin - read/write, if as a user - read only request.
    """

    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS and request.user and request.user.is_authenticated
        ) or (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Roles.ADMIN
        )#the request may not have a user if it is anonymous or none, because without this there is no one to ask and there will be an error
