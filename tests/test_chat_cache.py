"""Redis key format;
a cache hit does not access the database;
a cache miss reads from the database and populates Redis;
an empty history [] is a valid cached value."""

from unittest.mock import AsyncMock, Mock

import ai_bot.consumers as consumers


def test_dialog_messages_cache_key_contains_dialog_id():
    result = consumers.dialog_messages_cache_key(42)

    assert result == "chat:dialog:42:messages"


async def test_load_dialog_messages_uses_cached_history(monkeypatch):
    cached_messages = [
        {
            "role": "user",
            "content": "Hello",
        }
    ]

    get_from_cache = AsyncMock(return_value=cached_messages)
    load_from_db = AsyncMock()
    set_in_cache = AsyncMock()

    monkeypatch.setattr(
        consumers,
        "get_cached_dialog_messages",
        get_from_cache,
    )
    monkeypatch.setattr(
        consumers,
        "load_dialog_messages_from_db",
        load_from_db,
    )
    monkeypatch.setattr(
        consumers,
        "set_cached_dialog_messages",
        set_in_cache,
    )

    result = await consumers.load_dialog_messages(42)

    assert result == cached_messages
    get_from_cache.assert_awaited_once_with(42)
    load_from_db.assert_not_awaited()
    set_in_cache.assert_not_awaited()


async def test_load_dialog_messages_uses_db_after_cache_miss(monkeypatch):
    database_messages = [
        {
            "role": "assistant",
            "content": "How can I help?",
        }
    ]

    get_from_cache = AsyncMock(return_value=None)
    load_from_db = AsyncMock(return_value=database_messages)
    set_in_cache = AsyncMock()

    monkeypatch.setattr(
        consumers,
        "get_cached_dialog_messages",
        get_from_cache,
    )
    monkeypatch.setattr(
        consumers,
        "load_dialog_messages_from_db",
        load_from_db,
    )
    monkeypatch.setattr(
        consumers,
        "set_cached_dialog_messages",
        set_in_cache,
    )

    result = await consumers.load_dialog_messages(42)

    assert result == database_messages
    get_from_cache.assert_awaited_once_with(42)
    load_from_db.assert_awaited_once_with(42)
    set_in_cache.assert_awaited_once_with(
        42,
        database_messages,
    )


async def test_empty_cached_history_is_not_a_cache_miss(monkeypatch):
    get_from_cache = AsyncMock(return_value=[])
    load_from_db = AsyncMock()
    set_in_cache = AsyncMock()

    monkeypatch.setattr(
        consumers,
        "get_cached_dialog_messages",
        get_from_cache,
    )
    monkeypatch.setattr(
        consumers,
        "load_dialog_messages_from_db",
        load_from_db,
    )
    monkeypatch.setattr(
        consumers,
        "set_cached_dialog_messages",
        set_in_cache,
    )

    result = await consumers.load_dialog_messages(42)

    assert result == []
    load_from_db.assert_not_awaited()
    set_in_cache.assert_not_awaited()


async def test_save_chat_message_updates_existing_cache(monkeypatch):
    cached_messages = [
        {
            "role": "assistant",
            "content": "How can I help?",
        }
    ]
    saved_message = object()

    save_to_db = AsyncMock(return_value=saved_message)
    get_from_cache = AsyncMock(return_value=cached_messages)
    set_in_cache = AsyncMock()

    monkeypatch.setattr(
        consumers,
        "save_chat_message_to_db",
        save_to_db,
    )
    monkeypatch.setattr(
        consumers,
        "get_cached_dialog_messages",
        get_from_cache,
    )
    monkeypatch.setattr(
        consumers,
        "set_cached_dialog_messages",
        set_in_cache,
    )

    result = await consumers.save_chat_message(
        42,
        "user",
        "Show me available flights",
    )

    assert result is saved_message
    save_to_db.assert_awaited_once_with(
        42,
        "user",
        "Show me available flights",
    )
    get_from_cache.assert_awaited_once_with(42)
    set_in_cache.assert_awaited_once_with(
        42,
        [
            {
                "role": "assistant",
                "content": "How can I help?",
            },
            {
                "role": "user",
                "content": "Show me available flights",
            },
        ],
    )


async def test_save_chat_message_does_not_rebuild_missing_cache(monkeypatch):
    saved_message = object()

    save_to_db = AsyncMock(return_value=saved_message)
    get_from_cache = AsyncMock(return_value=None)
    set_in_cache = AsyncMock()

    monkeypatch.setattr(
        consumers,
        "save_chat_message_to_db",
        save_to_db,
    )
    monkeypatch.setattr(
        consumers,
        "get_cached_dialog_messages",
        get_from_cache,
    )
    monkeypatch.setattr(
        consumers,
        "set_cached_dialog_messages",
        set_in_cache,
    )

    result = await consumers.save_chat_message(
        42,
        "user",
        "Hello",
    )

    assert result is saved_message
    save_to_db.assert_awaited_once_with(
        42,
        "user",
        "Hello",
    )
    get_from_cache.assert_awaited_once_with(42)
    set_in_cache.assert_not_awaited()


async def test_save_chat_message_stops_when_db_write_is_skipped(monkeypatch):
    save_to_db = AsyncMock(return_value=None)
    get_from_cache = AsyncMock()
    set_in_cache = AsyncMock()

    monkeypatch.setattr(
        consumers,
        "save_chat_message_to_db",
        save_to_db,
    )
    monkeypatch.setattr(
        consumers,
        "get_cached_dialog_messages",
        get_from_cache,
    )
    monkeypatch.setattr(
        consumers,
        "set_cached_dialog_messages",
        set_in_cache,
    )

    result = await consumers.save_chat_message(
        0,
        "user",
        "Hello",
    )

    assert result is None
    get_from_cache.assert_not_awaited()
    set_in_cache.assert_not_awaited()


async def test_cache_read_error_is_treated_as_cache_miss(monkeypatch):
    fake_cache = Mock()
    fake_cache.aget = AsyncMock(
        side_effect=ConnectionError("Redis is unavailable")
    )

    monkeypatch.setattr(
        consumers,
        "cache",
        fake_cache,
    )

    result = await consumers.get_cached_dialog_messages(42)

    assert result is None
    fake_cache.aget.assert_awaited_once_with(
        "chat:dialog:42:messages"
    )


async def test_cache_write_error_does_not_escape(monkeypatch):
    messages = [
        {
            "role": "user",
            "content": "Hello",
        }
    ]

    fake_cache = Mock()
    fake_cache.aset = AsyncMock(
        side_effect=ConnectionError("Redis is unavailable")
    )

    monkeypatch.setattr(
        consumers,
        "cache",
        fake_cache,
    )

    result = await consumers.set_cached_dialog_messages(
        42,
        messages,
    )

    assert result is None
    fake_cache.aset.assert_awaited_once_with(
        "chat:dialog:42:messages",
        messages,
    )
