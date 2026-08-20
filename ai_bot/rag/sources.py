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
REFERENCE_SOURCE = "db:reference_data"


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


def reference_data_source() -> SourceData:
    """Index the slow-moving reference tables.

    Flights are deliberately excluded: they change by the minute and exact
    queries like "KBP to JFK tomorrow" belong in SQL, not in a vector search.
    """
    from airports.models import Airline, Airplane, Airport, City, Country

    chunks = []

    for country in Country.objects.all():
        chunks.append(
            Chunk(
                content=f"{country.name} is a country with the code {country.code}.",
                metadata={"kind": "country", "id": country.id, "code": country.code},
            )
        )

    for city in City.objects.select_related("country"):
        chunks.append(
            Chunk(
                content=f"{city.name} is a city in {city.country.name} ({city.country.code}).",
                metadata={"kind": "city", "id": city.id},
            )
        )

    for airport in Airport.objects.select_related("city", "country"):
        chunks.append(
            Chunk(
                content=(
                    f"Airport with the code {airport.code} serves the city of "
                    f"{airport.city.name} in {airport.country.name} ({airport.country.code})."
                ),
                metadata={"kind": "airport", "id": airport.id, "code": airport.code},
            )
        )

    for airline in Airline.objects.select_related("country").prefetch_related("airport"):
        parts = [f"{airline.name} is an airline"]
        if airline.country:
            parts.append(f"based in {airline.country.name}")
        if airline.founded_year:
            parts.append(f"founded in {airline.founded_year}")
        if airline.headquarters:
            parts.append(f"headquartered in {airline.headquarters}")
        codes = ", ".join(sorted(a.code for a in airline.airport.all()))
        if codes:
            parts.append(f"operating from airports {codes}")
        chunks.append(
            Chunk(
                content=", ".join(parts) + ".",
                metadata={"kind": "airline", "id": airline.id},
            )
        )

    for airplane in Airplane.objects.select_related("airline"):
        chunks.append(
            Chunk(
                content=(
                    f"Airplane {airplane.model} with registration number "
                    f"{airplane.reg_number} is operated by {airplane.airline.name}."
                ),
                metadata={"kind": "airplane", "id": airplane.id},
            )
        )

    return SourceData(REFERENCE_SOURCE, chunks=chunks)


def collect_sources() -> list[SourceData]:
    return [phone_book_source(), parking_source(), reference_data_source()]
