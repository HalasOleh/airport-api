from django.urls import re_path
from .consumers import TestConsumer

websocket_urlpatterns = [
    re_path(r"ws/test/$", TestConsumer.as_asgi()),
    re_path(r"ws/chat/(?P<dialog_id>\d+)/$", TestConsumer.as_asgi()),
]
