from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_bot.models import ChatDialog, ChatMessage
from ai_bot.serializers import ChatDialogSerializer, ChatMessageSerializer


class ChatDialogViewSet(viewsets.ModelViewSet):
    serializer_class = ChatDialogSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return ChatDialog.objects.filter(user=self.request.user).prefetch_related("messages")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        dialog = self.get_object()
        serializer = ChatMessageSerializer(dialog.messages.all(), many=True)
        return Response(serializer.data)


class ChatMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChatMessageSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("dialog", "role")

    def get_queryset(self):
        return ChatMessage.objects.filter(dialog__user=self.request.user)
