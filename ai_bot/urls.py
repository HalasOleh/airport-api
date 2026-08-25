from django.urls import path, include
from django.views.generic import TemplateView

from rest_framework import routers
from ai_bot.views import ChatDialogViewSet, ChatMessageViewSet

app_name = 'ai_bot'

router = routers.DefaultRouter()
router.register('api/chat/dialogs', ChatDialogViewSet, basename='chat-dialog')
router.register('api/chat/messages', ChatMessageViewSet, basename='chat-message')

urlpatterns = [
    path(
        'ws-page/',
        TemplateView.as_view(template_name='airports/ws_test.html'),
        name='ws-test-page',
    ),
    path('', include(router.urls)),

]
