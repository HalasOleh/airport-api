"""Similarity search over the knowledge base, with an exact-lookup safety net."""
import logging

from pgvector.django import CosineDistance

from ai_bot.models import KnowledgeChunk
from ai_bot.rag import fallback
from ai_bot.rag.embeddings import embed_query

logger = logging.getLogger(__name__)

# How many passages to hand back to the model. Four is enough to cover a
# question that spans two chunks without flooding the prompt with tokens.
DEFAULT_TOP_K = 4
MAX_TOP_K = 10

# There is deliberately no similarity cut-off here.
#
# Measured on this corpus with multilingual-e5-small, cosine distance came out
# as: relevant 0.112 / 0.123 / 0.157 / 0.172 / 0.188 / 0.198, irrelevant 0.214.
# The bands overlap, so any threshold either drops good hits ("Boryspil" sat
# 0.012 away from being discarded) or lets bad ones through. A number tuned on
# six samples is a guess wearing a lab coat.
#
# So retrieval reports evidence instead of pretending to judge it: every hit
# comes back with its similarity score, and the system prompt makes the model
# decide whether the passages actually answer the question. The model has the
# question, the passages and the scores; this function has only the scores.


def _exact_lookup(query: str) -> dict | None:
    """Read the answer straight off disk when the vector index has nothing.

    Only reachable when the index is empty or was never built - the files
    themselves are still there, so a question with an exact department or
    airport name in it can still be answered.
    """
    for lookup in (fallback.get_phone_number, fallback.get_place):
        result = lookup(query)
        if result.get("condition") == "available":
            logger.info("Empty index, %s answered from disk", lookup.__name__)
            return result
    return None


def search_knowledge_base(query: str, top_k: int = DEFAULT_TOP_K) -> dict:
    """Find the passages that answer `query`.

    Always reports a `condition` of "available" or "unknown" so the model can
    tell a real answer from a miss.
    """
    query = (query or "").strip()
    if not query:
        return {"query": query, "matches": [], "condition": "unknown",
                "detail": "Empty query"}

    try:
        top_k = max(1, min(int(top_k), MAX_TOP_K))
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K

    try:
        vector = embed_query(query)
    except Exception as exc:
        logger.exception("Could not embed the query")
        return {"query": query, "matches": [], "condition": "unknown",
                "detail": f"Embedding model unavailable: {exc}"}

    # This is the actual similarity search. CosineDistance compiles to the
    # pgvector `<=>` operator, so Postgres does the comparison itself and the
    # HNSW index on the embedding column keeps it fast as the corpus grows.
    # Ordering by distance ascending puts the closest meaning first.
    rows = list(
        KnowledgeChunk.objects
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance")
        .values("content", "metadata", "distance", "source__name")[:top_k]
    )

    if not rows:
        # Nothing indexed at all. This is the one case the deterministic
        # lookups genuinely rescue: the files are still on disk even when the
        # vector index is empty or was never built.
        logger.warning("Knowledge base is empty - run `manage.py reindex_kb`")
        exact = _exact_lookup(query)
        if exact:
            return {"query": query, "retrieval": "exact-lookup", **exact}
        return {"query": query, "matches": [], "condition": "unknown",
                "detail": "Knowledge base is empty"}

    matches = [
        {
            "content": row["content"],
            "source": row["source__name"],
            "metadata": row["metadata"],
            "similarity": round(1 - row["distance"], 3),
        }
        for row in rows
    ]
    logger.info(
        "Vector search for %r: %s hits, best similarity %.3f",
        query, len(matches), matches[0]["similarity"],
    )

    return {
        "query": query,
        "retrieval": "vector-search",
        # "available" means the search ran and returned passages - not that they
        # answer the question. That call belongs to the model.
        "condition": "available",
        "best_similarity": matches[0]["similarity"],
        "matches": matches,
    }
