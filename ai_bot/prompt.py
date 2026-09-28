"""Assemble the system prompt from prompts/system_prompt.yaml.

The prompt lives in YAML so it can be tuned without editing Python, and it is
built per connection rather than at import: it carries the current date, and a
module-level constant would freeze whatever day the worker started on.
"""
import logging
from pathlib import Path

import yaml
from django.utils import timezone

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "system_prompt.yaml"

# Used only if the YAML cannot be read. A bot that answers everything is worse
# than a bot that is briefly unhelpful, so the fallback keeps the limit.
FALLBACK_PROMPT = (
    "You are an airport assistant. You answer only questions about airports and "
    "air travel, using the tools you were given for anything about flights, "
    "fares, seats or bookings. Never request payment-card details, and never "
    "claim a booking or payment succeeded without a successful tool result. "
    "Refuse everything else with: \"Sorry, I can't answer that - I'm an airport "
    "assistant.\""
)

_cache: dict | None = None


def _load() -> dict:
    """Read and cache the YAML. Parsed once per process, not once per message."""
    global _cache

    if _cache is None:
        _cache = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))

    return _cache


def _flatten(block) -> list[str]:
    """A block is either text or a mapping of named sub-blocks (tool_rules)."""
    if isinstance(block, str):
        return [block.strip()]
    if isinstance(block, dict):
        return [part.strip() for part in block.values() if isinstance(part, str)]
    return []


def build_system_prompt(today=None) -> str:
    """The full system prompt, with today's date substituted in."""
    try:
        data = _load()
    except (OSError, yaml.YAMLError):
        logger.exception("Could not load %s, falling back to the built-in prompt", PROMPT_FILE)
        data = None

    if not isinstance(data, dict):
        return FALLBACK_PROMPT

    order = data.get("order") or [key for key in data if key != "order"]
    parts = []
    for key in order:
        parts.extend(_flatten(data.get(key)))

    prompt = "\n\n".join(part for part in parts if part)
    if not prompt:
        return FALLBACK_PROMPT

    today = today or timezone.localdate()
    # str.replace, not str.format: the prompt contains literal braces and a
    # format call would raise on them.
    return prompt.replace("{{today}}", today.isoformat())
