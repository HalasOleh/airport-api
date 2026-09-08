"""Chunking and retrieval.

The embedding model is not loaded here: these tests are about the shape of the
pipeline, not about how good the vectors are. Model quality is measured
separately, by hand, against a labelled set of queries.
"""
from unittest.mock import patch

import pytest

from ai_bot.rag import sources


def test_phone_book_is_chunked_per_department():
    source = sources.phone_book_source()

    assert source.ok
    assert len(source.chunks) == 4
    assert all(chunk.metadata["kind"] == "phone" for chunk in source.chunks)
    assert any("Technical Support" in c.content for c in source.chunks)


def test_parking_is_chunked_per_airport():
    source = sources.parking_source()

    assert source.ok
    assert len(source.chunks) == 6
    assert any("Boryspil" in c.content for c in source.chunks)


def test_reference_tables_are_no_longer_embedded():
    """Short categorical rows like "Kyiv is a city in Ukraine (UA)." were the
    wrong thing to embed, and they crowded out the parking and contact text that
    actually needs semantics. They are served by ai_bot/tools/reference_tools.py
    now, so nothing should reintroduce them here."""
    names = [source.name for source in sources.collect_sources()]

    assert names == [sources.PHONE_SOURCE, sources.PARKING_SOURCE]


def test_checksum_follows_content_not_the_file():
    """The hash covers the produced chunk text, so reformatting a file that
    yields identical chunks is correctly skipped on re-index."""
    first = sources.phone_book_source().checksum
    second = sources.phone_book_source().checksum

    assert first == second
    assert first != sources.parking_source().checksum


def test_missing_file_is_reported_not_raised():
    with patch.object(sources, "load_phone_book", side_effect=FileNotFoundError):
        source = sources.phone_book_source()

    # A broken source must not wipe the chunks that are already indexed.
    assert not source.ok
    assert source.chunks == []
    assert "not found" in source.error


def test_malformed_file_is_reported_not_raised():
    with patch.object(sources, "load_phone_book", side_effect=SyntaxError("bad literal")):
        source = sources.phone_book_source()

    assert not source.ok
    assert "malformed" in source.error


@pytest.mark.django_db
def test_retired_sources_are_deleted_from_the_index():
    """Retiring a source in the code has to remove it from the database too.

    collect_sources() only iterates over sources that still exist, so without an
    explicit prune the retired KnowledgeSource row and every one of its chunks
    stay indexed forever and keep coming back from vector search - the
    retirement would have no effect at all.
    """
    from ai_bot.models import KnowledgeChunk, KnowledgeSource
    from ai_bot.rag.indexer import prune_removed_sources

    retired = KnowledgeSource.objects.create(
        name="db:reference_data", checksum="stale", chunk_count=1
    )
    KnowledgeChunk.objects.create(
        source=retired, content="Kyiv is a city in Ukraine (UA).", embedding=[0.0] * 384
    )

    removed = prune_removed_sources(sources.collect_sources())

    assert removed == ["db:reference_data"]
    assert not KnowledgeSource.objects.filter(name="db:reference_data").exists()
    # The chunks cascade with the row, so nothing is left to be retrieved.
    assert KnowledgeChunk.objects.count() == 0


@pytest.mark.django_db
def test_a_source_that_failed_to_load_is_not_pruned():
    """A file that is temporarily broken is not evidence that it was removed.
    Wiping its chunks would repeat the mistake reindex_source() avoids."""
    from ai_bot.models import KnowledgeSource
    from ai_bot.rag.indexer import prune_removed_sources

    KnowledgeSource.objects.create(
        name=sources.PHONE_SOURCE, checksum="whatever", chunk_count=4
    )
    broken = sources.SourceData(sources.PHONE_SOURCE, error="file is on fire")

    removed = prune_removed_sources([broken, sources.parking_source()])

    assert removed == []
    assert KnowledgeSource.objects.filter(name=sources.PHONE_SOURCE).exists()


@pytest.mark.django_db
def test_empty_index_falls_back_to_exact_lookup():
    from ai_bot.rag import retrieval

    with patch.object(retrieval, "embed_query", return_value=[0.0] * 384):
        result = retrieval.search_knowledge_base("Technical Support")

    # Nothing is indexed in the test database, so the deterministic lookup is
    # the only thing that can answer - and it can, because the files are there.
    assert result["retrieval"] == "exact-lookup"
    assert result["condition"] == "available"
    assert result["department"] == "Technical Support"


@pytest.mark.django_db
def test_empty_index_and_no_match_says_unknown():
    from ai_bot.rag import retrieval

    with patch.object(retrieval, "embed_query", return_value=[0.0] * 384):
        result = retrieval.search_knowledge_base("something that does not exist")

    assert result["condition"] == "unknown"


@pytest.mark.django_db
def test_empty_query_is_rejected_before_embedding():
    from ai_bot.rag import retrieval

    with patch.object(retrieval, "embed_query") as embed:
        result = retrieval.search_knowledge_base("   ")

    embed.assert_not_called()
    assert result["condition"] == "unknown"
