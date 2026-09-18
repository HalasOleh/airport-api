from datetime import date
from unittest.mock import Mock

import ai_bot.prompt as prompt_module


def test_build_system_prompt_preserves_order_and_replaces_date(
    monkeypatch,
):
    prompt_data = {
        "order": [
            "identity",
            "rules",
        ],
        "identity": "Today is {{today}}.",
        "rules": {
            "first": "Use airport tools.",
            "second": "Do not invent flights.",
        },
    }  

    load_prompt = Mock(return_value=prompt_data)

    monkeypatch.setattr(
        prompt_module,
        "_load",
        load_prompt,
    )

    result = prompt_module.build_system_prompt(
        today=date(2026, 9, 17)
    )

    assert result == (
        "Today is 2026-09-17.\n\n"
        "Use airport tools.\n\n"
        "Do not invent flights."
    )
    load_prompt.assert_called_once_with()


def test_build_system_prompt_uses_fallback_when_file_cannot_be_read(
    monkeypatch,
):
    load_prompt = Mock(
        side_effect=OSError("Prompt file is unavailable")
    )

    monkeypatch.setattr(
        prompt_module,
        "_load",
        load_prompt,
    )

    result = prompt_module.build_system_prompt(
        today=date(2026, 9, 17)
    )

    assert result == prompt_module.FALLBACK_PROMPT
    load_prompt.assert_called_once_with()


def test_build_system_prompt_uses_fallback_for_empty_content(
    monkeypatch,
):
    load_prompt = Mock(
        return_value={
            "order": ["identity"],
            "identity": "",
        }
    )

    monkeypatch.setattr(
        prompt_module,
        "_load",
        load_prompt,
    )

    result = prompt_module.build_system_prompt(
        today=date(2026, 9, 17)
    )

    assert result == prompt_module.FALLBACK_PROMPT