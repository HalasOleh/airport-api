from rest_framework import serializers

from ai_bot.models import ChatDialog, ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ("id", "dialog", "role", "content", "created_at")
        read_only_fields = ("id", "created_at")


class ChatDialogSerializer(serializers.ModelSerializer):
    messages_count = serializers.IntegerField(source="messages.count", read_only=True)

    class Meta:
        model = ChatDialog
        fields = ("id", "title", "messages_count", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
