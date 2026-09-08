"""WebSocket handshake authentication.

WebsocketCommunicator drives the real ASGI stack - OriginValidator, the
Channels auth stack and JWTAuthMiddleware all run - so these tests cover the
cookie parsing that `new WebSocket()` depends on.
"""
import pytest
from channels.testing import WebsocketCommunicator
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

from ai_bot.models import ChatDialog
from config.asgi import application

ORIGIN = b"http://localhost:8000"


def _headers(cookie=None, origin=ORIGIN):
    headers = [(b"host", b"localhost:8000")]
    if origin:
        headers.append((b"origin", origin))
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return headers


async def _connect(dialog_id, **kwargs):
    communicator = WebsocketCommunicator(
        application, f"/ws/chat/{dialog_id}/", headers=_headers(**kwargs)
    )
    connected, _ = await communicator.connect(timeout=10)
    await communicator.disconnect()
    return connected


@pytest.fixture
def dialog(db, user):
    return ChatDialog.objects.create(user=user)


@pytest.fixture
def access_token(db, user):
    return str(RefreshToken.for_user(user).access_token)


@pytest.mark.django_db(transaction=True)
async def test_cookie_authenticates_the_handshake(dialog, access_token):
    cookie = f"{settings.JWT_ACCESS_COOKIE}={access_token}"
    assert await _connect(dialog.id, cookie=cookie) is True


@pytest.mark.django_db(transaction=True)
async def test_handshake_without_a_cookie_is_refused(dialog):
    assert await _connect(dialog.id) is False


@pytest.mark.django_db(transaction=True)
async def test_garbage_token_is_refused(dialog):
    cookie = f"{settings.JWT_ACCESS_COOKIE}=not-a-jwt"
    assert await _connect(dialog.id, cookie=cookie) is False


@pytest.mark.django_db(transaction=True)
async def test_foreign_origin_is_refused(dialog, access_token):
    """WebSockets are exempt from the same-origin policy and a CSRF token
    cannot be sent on a handshake, so Origin is the only defence against
    cross-site WebSocket hijacking."""
    cookie = f"{settings.JWT_ACCESS_COOKIE}={access_token}"
    assert await _connect(dialog.id, cookie=cookie, origin=b"http://evil.example.com") is False


@pytest.mark.django_db(transaction=True)
async def test_another_users_dialog_is_refused(other_user, dialog, access_token):
    stranger_dialog = await ChatDialog.objects.acreate(user=other_user)
    cookie = f"{settings.JWT_ACCESS_COOKIE}={access_token}"
    assert await _connect(stranger_dialog.id, cookie=cookie) is False
