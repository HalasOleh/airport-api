"""File readers, plus the last-resort lookups used when the index is empty.

load_phone_book() and load_parking_blocks() are the real interface here; the
chat bot's get_contacts tool reads the phone book through the first of them.

get_phone_number() and get_place() below are NOT part of the tool path, and the
substring matching in them is not a pattern to copy. Deciding which department
or airport someone means is the model's job - it survives rephrasing and knows
what was said three turns ago, neither of which a substring match can do. These
two are reached only from retrieval._exact_lookup(), when the vector index is
empty or was never built and the files on disk are all that is left.
"""
import ast
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
PHONE_FILE = KNOWLEDGE_BASE_DIR / "phone_numbers.txt"
PARKING_FILE = KNOWLEDGE_BASE_DIR / "parking_info.txt"


def load_phone_book() -> dict:
    """Read the phone book, stored as a Python dict literal in a .txt file."""
    raw = PHONE_FILE.read_text(encoding="utf-8")
    _, _, literal = raw.partition("=")
    return ast.literal_eval(literal.strip())


def load_parking_blocks() -> list[str]:
    """Read parking info as blank-line separated blocks, one per airport."""
    raw = PARKING_FILE.read_text(encoding="utf-8")
    blocks = [block.strip() for block in raw.split("\n\n") if block.strip()]
    # The first block is the file heading, not an airport.
    return blocks[1:] if blocks and "\n" not in blocks[0] else blocks


def get_phone_number(department: str) -> dict:
    try:
        phone_book = load_phone_book()
    except FileNotFoundError:
        logger.warning("Phone numbers file missing at %s", PHONE_FILE)
        return {
            "department": department,
            "phone_number": "Phone numbers file not found",
            "condition": "unknown",
        }
    except (ValueError, SyntaxError) as exc:
        logger.error("Phone numbers file is malformed: %s", exc)
        return {
            "department": department,
            "phone_number": f"Phone numbers file is malformed: {exc}",
            "condition": "unknown",
        }

    query = (department or "").strip().lower()
    for name, info in phone_book.items():
        if query and (query in name.lower() or name.lower() in query):
            return {
                "department": name,
                "contact_data": info,
                "condition": "available",
            }

    return {
        "department": department,
        "phone_number": "No phone number found for this department",
        "available_departments": list(phone_book),
        "condition": "unknown",
    }


def get_place(airport: str) -> dict:
    try:
        blocks = load_parking_blocks()
    except FileNotFoundError:
        logger.warning("Parking info file missing at %s", PARKING_FILE)
        return {
            "airport": airport,
            "place": "Parking information file not found",
            "condition": "unknown",
        }
    except OSError as exc:
        logger.error("Cannot read parking info: %s", exc)
        return {
            "airport": airport,
            "place": f"Error reading parking info: {exc}",
            "condition": "unknown",
        }

    query = (airport or "").strip().lower()
    for block in blocks:
        if query and query in block.lower():
            return {
                "airport": airport,
                "place": block,
                "condition": "available",
                "source": "ai_bot/knowledge_base/parking_info.txt",
            }

    return {
        "airport": airport,
        "place": "No parking information found for this airport",
        "condition": "unknown",
        "source": "ai_bot/knowledge_base/parking_info.txt",
    }
