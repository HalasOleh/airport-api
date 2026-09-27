# ai_bot/middleware.py

from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_from_token(token):
    try:
        access_token = AccessToken(token)
        user_id = access_token["user_id"]
        return get_user_model().objects.get(id=user_id)
    except (TokenError, get_user_model().DoesNotExist, KeyError):
        return AnonymousUser()


def token_from_cookies(scope) -> str | None:
    """Pull the access token out of the raw Cookie header in the ASGI scope.

    There is no request object at this layer - scope["headers"] is a list of
    raw (name, value) byte pairs - so the header has to be found and parsed by
    hand. SimpleCookie handles the quoting and separator rules of the cookie
    format, which are fiddly enough not to reimplement with split(";").
    """
    for name, value in scope.get("headers", []):
        if name != b"cookie":
            continue
        cookies = SimpleCookie()
        try:
            cookies.load(value.decode("latin-1"))
        except Exception:
            return None
        morsel = cookies.get(settings.JWT_ACCESS_COOKIE)
        return morsel.value if morsel else None
    return None


class JWTAuthMiddleware:
    """Authenticate a WebSocket from a cookie, a query parameter, or a session.

    Sources are tried most-explicit first:

    1. ``?token=`` - for non-browser clients that cannot hold cookies.
    2. the access-token cookie - what a browser sends automatically, and the
       only mechanism that works from ``new WebSocket()``, which has no way to
       set an Authorization header.
    3. whatever AuthMiddlewareStack already resolved from the Django session.

    Must stay wrapped in AuthMiddlewareStack so that (3) is already populated
    in scope["user"] before this runs.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_params = parse_qs(scope.get("query_string", b"").decode())
        token = query_params.get("token", [None])[0] or token_from_cookies(scope)

        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope.setdefault("user", AnonymousUser())

        return await self.app(scope, receive, send)
