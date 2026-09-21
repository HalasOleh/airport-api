# ai_bot/middleware.py

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError


@database_sync_to_async
def get_user_from_token(token):
    try:
        access_token = AccessToken(token)
        user_id = access_token["user_id"]
        return get_user_model().objects.get(id=user_id)
    except (TokenError, get_user_model().DoesNotExist, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware:
    """Authenticate a WebSocket by JWT, falling back to the Django session.

    Must be wrapped in AuthMiddlewareStack so that session auth has already
    populated scope["user"] by the time this runs; a ?token= query parameter
    then takes precedence for non-browser clients.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope.setdefault("user", AnonymousUser())

        return await self.app(scope, receive, send)
