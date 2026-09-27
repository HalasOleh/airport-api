import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.asgi import get_asgi_application
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler


from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# Initialize Django before importing app routing that touches models/consumers.
django_asgi_app = get_asgi_application()

from ai_bot.middleware import JWTAuthMiddleware
from ai_bot.routing import websocket_urlpatterns

application = ASGIStaticFilesHandler(ProtocolTypeRouter({
    "http": django_asgi_app,
    # AllowedHostsOriginValidator is not optional once the token lives in a
    # cookie. WebSockets are exempt from the same-origin policy: any page on
    # any site can open ws://localhost:8000/ws/chat/1/ and the browser will
    # attach our cookie to the handshake, handing that site an authenticated
    # socket (cross-site WebSocket hijacking). Nothing in the CSRF machinery
    # covers this - CSRF tokens cannot be sent on a handshake at all. Checking
    # the Origin header against ALLOWED_HOSTS is the defence.
    "websocket": AllowedHostsOriginValidator(
        # AuthMiddlewareStack first (session auth), then JWT overrides it from
        # the cookie or a ?token= query parameter.
        AuthMiddlewareStack(
            JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
        )
    ),
}))
