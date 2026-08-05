"""
Embedder — chunks text and generates sentence-transformer embeddings.
Uses all-MiniLM-L6-v2 (384-dim, free, no API key needed).
Singleton pattern so model loads once at startup.
"""
import re
from functools import lru_cache
from typing import Optional

from sentence_transformers import SentenceTransformer
from app.config import get_settings

settings = get_settings()

_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """Singleton — loads model once."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed a list of text strings. Returns list of 384-dim vectors."""
    model = get_embedding_model()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()


def embed_single(text: str) -> list[float]:
    """Embed a single string."""
    return embed_texts([text])[0]


def chunk_text(text: str, max_tokens: int = 500, overlap_tokens: int = 50) -> list[str]:
    """
    Split text into overlapping chunks by approximate token count.
    Approximation: 1 token ≈ 4 characters.
    """
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4

    if len(text) <= max_chars:
        return [text.strip()] if text.strip() else []

    # Split into sentences first
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) <= max_chars:
            current += " " + sentence
        else:
            if current.strip():
                chunks.append(current.strip())
            # Start new chunk with overlap from end of current
            current = current[-overlap_chars:] + " " + sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text[:max_chars].strip()]
