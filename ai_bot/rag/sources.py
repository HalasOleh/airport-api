"""Turn the knowledge base into chunks ready for embedding.

Chunking follows the natural boundaries of each source - one department, one
airport, one database row - instead of slicing at a fixed character count,
which would cut phone numbers and addresses in half.
"""
import hashlib
import logging
from dataclasses import dataclass, field

from ai_bot.rag.fallback import (
    PARKING_FILE,
    PHONE_FILE,
    load_parking_blocks,
    load_phone_book,
)

logger = logging.getLogger(__name__)

PHONE_SOURCE = "file:phone_numbers"
PARKING_SOURCE = "file:parking_info"


@dataclass
class Chunk:
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SourceData:
    """Chunks of one source, or the reason they could not be produced."""

    name: str
    chunks: list[Chunk] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def checksum(self) -> str:
        """Hash of the produced text, so any change that affects the index shows."""
        digest = hashlib.sha256()
        for chunk in self.chunks:
            digest.update(chunk.content.encode("utf-8"))
            digest.update(b"\x00")
        return digest.hexdigest()


def phone_book_source() -> SourceData:
    try:
        phone_book = load_phone_book()
    except FileNotFoundError:
        return SourceData(PHONE_SOURCE, error=f"Phone numbers file not found at {PHONE_FILE}")
    except (ValueError, SyntaxError) as exc:
        return SourceData(PHONE_SOURCE, error=f"Phone numbers file is malformed: {exc}")

    chunks = []
    for department, info in phone_book.items():
        details = ". ".join(f"{key}: {value}" for key, value in info.items())
        chunks.append(
            Chunk(
                content=f"{department} department of the airport. {details}.",
                metadata={"kind": "phone", "department": department, "contact_data": info},
            )
        )

    return SourceData(PHONE_SOURCE, chunks=chunks)


def parking_source() -> SourceData:
    try:
        blocks = load_parking_blocks()
    except FileNotFoundError:
        return SourceData(PARKING_SOURCE, error=f"Parking info file not found at {PARKING_FILE}")
    except OSError as exc:
        return SourceData(PARKING_SOURCE, error=f"Cannot read parking info: {exc}")

    chunks = [
        Chunk(
            content=f"Airport parking information. {block}",
            metadata={"kind": "parking", "airport": block.splitlines()[0].strip()},
        )
        for block in blocks
    ]

    return SourceData(PARKING_SOURCE, chunks=chunks)


def collect_sources() -> list[SourceData]:
    """The sources worth embedding.

    Only free text lives here now. The reference tables - countries, cities,
    airports, airlines, airplanes - used to be embedded too, and should not have
    been: "Kyiv is a city in Ukraine (UA)." is a short categorical string with no
    nuance for a vector to capture, so an exact `WHERE code = 'KBP'` beats
    similarity search on accuracy and cost alike. Worse, those chunks competed
    for the top-k against parking and contact text, where semantics do matter.
    They are served by ai_bot/tools/reference_tools.py instead.

    Flights were never indexed and still are not: they change by the minute, and
    "KBP to JFK tomorrow" is a question for SQL - see ai_bot/tools/flight_tools.py.
    """
    return [phone_book_source(), parking_source()]
