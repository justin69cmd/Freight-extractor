"""Embeddings — provider-agnostic with an offline deterministic fallback.

`openai` for production; `local` is a deterministic hashing embedder (no network,
no key) used in dev/tests so the RAG layer is exercisable end-to-end without a
provider. Both return unit-length vectors of `settings.embedding_dim`, so they
are interchangeable at the storage/query layer.
"""
from __future__ import annotations

import hashlib
import math
import re

from app.config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def embed(text: str) -> list[float]:
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "openai":
        return _openai_embed(texts)
    return [_local_embed(t) for t in texts]


def _openai_embed(texts: list[str]) -> list[list[float]]:
    # Graceful fallback so indexing/search never hard-fails when the SDK or key
    # is absent (e.g. local/dev). Production sets the key and SDK.
    if not settings.openai_api_key:
        return [_local_embed(t) for t in texts]
    try:
        from openai import OpenAI  # lazy
    except ImportError:
        return [_local_embed(t) for t in texts]
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.embeddings.create(model=settings.embedding_model, input=texts)
    return [d.embedding for d in resp.data]


def _local_embed(text: str, dim: int | None = None) -> list[float]:
    """Deterministic bag-of-tokens hashing embedding, L2-normalized.

    Similar texts share tokens -> similar vectors, which is enough for the
    hybrid retriever's re-ranking in dev/test. Not a substitute for a real model
    in production (set FREIGHT_EMBEDDING_PROVIDER=openai there)."""
    dim = dim or settings.embedding_dim
    vec = [0.0] * dim
    for tok in _TOKEN_RE.findall((text or "").lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 7) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
