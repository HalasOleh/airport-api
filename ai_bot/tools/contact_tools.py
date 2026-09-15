"""Airport department contacts.

Migrated off the substring matching in rag/fallback.get_phone_number, which
compared the query against every department name in both directions. That kind
of matching breaks the moment a user rephrases ("хто лагодить сайт") and has no
access to what was said earlier in the conversation. Deciding which department
someone means is exactly what the model is for; this function only reads a file.
"""
import logging

from ai_bot.rag import fallback

logger = logging.getLogger(__name__)


def _all_departments(phone_book: dict) -> list[dict]:
    return [{"department": name, **info} for name, info in phone_book.items()]


def get_contacts(department=None) -> dict:
    """Phone numbers and emails for the airport's departments.

    With no department named, returns all of them - the model can then pick the
    right one from the conversation instead of this code guessing from a string.
    """
    try:
        phone_book = fallback.load_phone_book()
    except FileNotFoundError:
        logger.warning("Phone numbers file missing at %s", fallback.PHONE_FILE)
        return {"error": "The department contact list is missing from the server."}
    except (ValueError, SyntaxError) as exc:
        logger.error("Phone numbers file is malformed: %s", exc)
        return {"error": f"The department contact list is malformed: {exc}"}

    if not department:
        return {"departments": _all_departments(phone_book)}

    wanted = str(department).strip().lower()
    for name, info in phone_book.items():
        if name.lower() == wanted:
            return {"department": name, **info}

    # No exact match: hand back the whole list and let the model choose, rather
    # than guessing with the substring match this function was written to replace.
    return {
        "detail": f"There is no department named {department!r}. These exist:",
        "departments": _all_departments(phone_book),
    }
 