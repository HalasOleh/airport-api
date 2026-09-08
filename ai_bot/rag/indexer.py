"""Build and refresh the vector index."""
import logging

from django.db import transaction

from ai_bot.models import KnowledgeChunk, KnowledgeSource
from ai_bot.rag.embeddings import embed_passages
from ai_bot.rag.sources import SourceData, collect_sources

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


def reindex_source(source: SourceData, force: bool = False) -> dict:
    """Re-embed one source if its content hash moved (or if forced)."""
    if not source.ok:
        # A broken source keeps whatever was indexed last time: wiping good
        # chunks because someone mistyped a file would make the bot worse.
        logger.warning("Skipping %s: %s", source.name, source.error)
        return {"source": source.name, "status": "error", "detail": source.error}

    # Embedding is the expensive step, so it only runs when the content really
    # changed. The checksum hashes the produced chunk text, not the raw file, so
    # a reformatted file that yields identical chunks is correctly skipped.
    record = KnowledgeSource.objects.filter(name=source.name).first()
    checksum = source.checksum

    if record and record.checksum == checksum and not force:
        logger.info("%s unchanged (%s chunks)", source.name, record.chunk_count)
        return {"source": source.name, "status": "unchanged", "chunks": record.chunk_count}

    logger.info("Embedding %s: %s chunks", source.name, len(source.chunks))
    contents = [chunk.content for chunk in source.chunks]

    vectors = []
    for start in range(0, len(contents), BATCH_SIZE):
        vectors.extend(embed_passages(contents[start:start + BATCH_SIZE]))

    # Replace the whole source in one transaction: a half-written index would
    # answer questions from a mix of old and new chunks.
    with transaction.atomic():
        record, _ = KnowledgeSource.objects.update_or_create(
            name=source.name,
            defaults={"checksum": checksum, "chunk_count": len(source.chunks)},
        )
        record.chunks.all().delete()
        KnowledgeChunk.objects.bulk_create([
            KnowledgeChunk(
                source=record,
                content=chunk.content,
                metadata=chunk.metadata,
                embedding=vector,
            )
            for chunk, vector in zip(source.chunks, vectors)
        ])

    logger.info("Indexed %s: %s chunks", source.name, len(source.chunks))
    return {"source": source.name, "status": "reindexed", "chunks": len(source.chunks)}


def prune_removed_sources(sources: list[SourceData]) -> list[str]:
    """Delete indexed sources that no longer exist in the code.

    Without this, retiring a source leaves its KnowledgeSource row and every one
    of its chunks in the database forever, and vector search keeps returning
    them - the retirement would have no effect at all.

    Appearing in collect_sources() at all is what counts as "still here" -
    including a source whose file failed to load. A broken file is not evidence
    that the source was retired, and deleting its chunks over a typo would
    repeat the mistake reindex_source() above is careful to avoid.
    """
    keep = [source.name for source in sources]
    removed = list(
        KnowledgeSource.objects.exclude(name__in=keep).values_list("name", flat=True)
    )
    if removed:
        # KnowledgeChunk.source cascades, so the chunks go with the row.
        KnowledgeSource.objects.filter(name__in=removed).delete()
        logger.info("Removed %s retired source(s): %s", len(removed), ", ".join(removed))
    return removed


def reindex_all(force: bool = False) -> list[dict]:
    sources = collect_sources()
    report = [reindex_source(source, force=force) for source in sources]

    for name in prune_removed_sources(sources):
        report.append({"source": name, "status": "removed", "chunks": 0})

    return report
