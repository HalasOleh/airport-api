"""Local embedding model.

The model is multilingual on purpose: users write in Ukrainian while the
knowledge base is in English, so a single-language model would fail to match
across the two.
"""
import logging
import os
import threading
from typing import Sequence

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-small")
EMBEDDING_DIM = 384

_model = None
_lock = threading.Lock()


def get_model():
    """Load the model once per process, guarded against concurrent first use."""
    global _model

    if _model is None:
        with _lock:
            if _model is None:
                # Imported lazily: torch takes seconds to import and is not
                # needed by processes that never embed anything.
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model %s", MODEL_NAME)
                _model = SentenceTransformer(MODEL_NAME)
                logger.info("Embedding model %s ready", MODEL_NAME)

    return _model


def embed_passages(texts: Sequence[str]) -> list[list[float]]:
    """Embed documents for storage."""
    if not texts:
        return []

    # e5 models are trained with these prefixes; dropping them measurably
    # degrades retrieval quality.
    prefixed = [f"passage: {text}" for text in texts]
    vectors = get_model().encode(prefixed, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]


def embed_query(text: str) -> list[float]:
    """Embed a user question for search."""
    vector = get_model().encode(f"query: {text}", normalize_embeddings=True)
    return vector.tolist()
