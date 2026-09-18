import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import ai_bot.consumers as consumers
from ai_bot.models import ChatMessage


async def test_ai_provider_error_returns_error_frame(monkeypatch):
    consumer = consumers.TestConsumer()

    consumer.provider = "openai"
    consumer.dialog = SimpleNamespace(id=42)
    consumer.messages = []
    consumer.send = AsyncMock()
    consumer.close = AsyncMock()
    consumer.generate_reply = AsyncMock(
        side_effect=RuntimeError("AI provider is unavailable")
    )

    save_message = AsyncMock()

    monkeypatch.setattr(
        consumers,
        "save_chat_message",
        save_message,
    )

    await consumer.receive(
        json.dumps(
            {
                "message": "Show me available flights",
            }
        )
    )

    assert consumer.messages == [
        {
            "role": "user",
            "content": "Show me available flights",
        }
    ]

    consumer.generate_reply.assert_awaited_once_with()

    save_message.assert_awaited_once_with(
        42,
        ChatMessage.Role.USER,
        "Show me available flights",
    )

    consumer.send.assert_awaited_once_with(
        text_data=json.dumps(
            {
                "error": "Failed to generate a reply",
            }
        )
    )

    consumer.close.assert_not_awaited()