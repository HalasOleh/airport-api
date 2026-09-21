import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.asgi import get_asgi_application
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler


from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

# Initialize Django before importing app routing that touches models/consumers.
django_asgi_app = get_asgi_application()

from ai_bot.middleware import JWTAuthMiddleware
from ai_bot.routing import websocket_urlpatterns

application = ASGIStaticFilesHandler(ProtocolTypeRouter({
    "http": django_asgi_app,
    # AuthMiddlewareStack first (session auth), then JWT overrides it when a
    # ?token= is supplied by a non-browser client.
    "websocket": AuthMiddlewareStack(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
}))
