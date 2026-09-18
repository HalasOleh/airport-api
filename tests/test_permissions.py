from unittest.mock import Mock

from config.permissions import IsAdminAllORIsAuthenticatedReadOnly
from user.models import User


def make_request(method, is_authenticated, role=User.Roles.USER):
    request = Mock()
    request.method = method

    request.user = Mock()
    request.user.is_authenticated = is_authenticated
    request.user.role = role

    return request


def test_authenticated_user_can_read():
    permission = IsAdminAllORIsAuthenticatedReadOnly()
    request = make_request("GET", is_authenticated=True)

    assert permission.has_permission(request, None) is True


def test_anonymous_user_cannot_read():
    permission = IsAdminAllORIsAuthenticatedReadOnly()
    request = make_request("GET", is_authenticated=False)

    assert permission.has_permission(request, None) is False


def test_regular_user_cannot_create():
    permission = IsAdminAllORIsAuthenticatedReadOnly()
    request = make_request(
        "POST",
        is_authenticated=True,
        role=User.Roles.USER,
    )

    assert permission.has_permission(request, None) is False


def test_admin_can_create():
    permission = IsAdminAllORIsAuthenticatedReadOnly()
    request = make_request(
        "POST",
        is_authenticated=True,
        role=User.Roles.ADMIN,
    )

    assert permission.has_permission(request, None) is True
