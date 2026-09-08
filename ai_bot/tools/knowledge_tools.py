"""Semantic search over the knowledge base, exposed as a tool.

Thin on purpose: the retrieval logic lives in ai_bot/rag/retrieval.py. This
exists so the vector path is dispatched through the same registry as everything
else, instead of the consumer keeping a second way to call a tool.

What stays behind the vector index is the text that actually has nuance to
capture - parking rules and department contact blurbs. The reference tables
moved to reference_tools, where an exact match is both cheaper and correct.
"""
import logging

from ai_bot.rag import retrieval
from ai_bot.tools.common import clamp_limit

logger = logging.getLogger(__name__)


def search_knowledge_base(query=None, top_k=None) -> dict:
    """Find knowledge base passages that may answer a question."""
    if not query:
        return {"error": "What should I search the knowledge base for?"}

    top_k = clamp_limit(
        top_k, default=retrieval.DEFAULT_TOP_K, maximum=retrieval.MAX_TOP_K
    )
    return retrieval.search_knowledge_base(str(query), top_k)
