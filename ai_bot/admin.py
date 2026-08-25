from django.contrib import admin

from ai_bot.models import ChatDialog, ChatMessage


@admin.register(ChatDialog)
class ChatDialogAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "created_at", "updated_at")
    search_fields = ("title", "user__email")
    list_filter = ("created_at", "updated_at")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "dialog", "role", "created_at")
    search_fields = ("content", "dialog__title", "dialog__user__email")
    list_filter = ("role", "created_at")
