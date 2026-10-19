"""Embedding providers. Credentials come from settings/environment only - never from code.

Supported (EMBEDDING_PROVIDER):
  local   sentence-transformers model (default BAAI/bge-large-en-v1.5, 1024-d, English)
  openai  OpenAI embeddings API (model + native `dimensions` parameter; needs EMBEDDING_API_KEY)
  test    deterministic hash vectors for tests ONLY - carries no semantic meaning, refused in production
"""
from __future__ import annotations

import asyncio
import hashlib
import math
from typing import Protocol

import httpx

from app.core.config import settings


class EmbeddingError(Exception):
    """Provider failure. `retryable` says whether trying the same batch again could help."""

    def __init__(self, message: str, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.retryable, self.retry_after = retryable, retry_after


class DimensionMismatch(EmbeddingError):
    """The provider returned vectors that do not match the database column. Never truncated or padded."""


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def check_dimensions(vectors: list[list[float]], expected: int, n_inputs: int) -> None:
    if len(vectors) != n_inputs:
        raise EmbeddingError(f"provider returned {len(vectors)} vectors for {n_inputs} inputs")
    for v in vectors:
        if len(v) != expected:
            raise DimensionMismatch(f"embedding has {len(v)} dimensions but the database expects {expected}; "
                                    "change the model or the vector(N) column deliberately - never truncate or pad")
        if not all(math.isfinite(x) for x in v):
            raise EmbeddingError("provider returned a non-finite value")


class DeterministicTestProvider:
    """Hash-derived unit vectors. Identical text -> identical vector; NO semantic similarity."""

    name = "test"

    def __init__(self, dimension: int | None = None, model: str = "test-deterministic-v1"):
        self.dimension, self.model = dimension or settings.EMBEDDING_DIMENSION, model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            raw = b""
            i = 0
            while len(raw) < self.dimension * 2:
                raw += hashlib.sha256(f"{i}:{t}".encode()).digest()
                i += 1
            vec = [(raw[2 * k] * 256 + raw[2 * k + 1]) / 32768.0 - 1.0 for k in range(self.dimension)]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


class LocalSentenceTransformerProvider:
    name = "local"

    def __init__(self, model: str | None = None, dimension: int | None = None):
        self.model = model or settings.EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise EmbeddingError("sentence-transformers is not installed (pip install sentence-transformers)") from e
            self._model = SentenceTransformer(self.model)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        def _run():
            m = self._load()
            return m.encode(texts, normalize_embeddings=True, convert_to_numpy=True).tolist()

        vectors = await asyncio.to_thread(_run)
        check_dimensions(vectors, self.dimension, len(texts))
        return vectors


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None, dimension: int | None = None,
                 client: httpx.AsyncClient | None = None, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key if api_key is not None else settings.EMBEDDING_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self._client, self._base = client, base_url

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingError("EMBEDDING_API_KEY is not set")
        payload = {"model": self.model, "input": texts, "dimensions": self.dimension}
        client = self._client or httpx.AsyncClient(timeout=60)
        try:
            r = await client.post(f"{self._base}/embeddings", json=payload,
                                  headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.TransportError as e:
            raise EmbeddingError(f"network error: {e}", retryable=True) from e
        finally:
            if self._client is None:
                await client.aclose()
        if r.status_code == 429:
            raise EmbeddingError("rate limited", retryable=True, retry_after=float(r.headers.get("retry-after", 1)))
        if r.status_code >= 500:
            raise EmbeddingError(f"provider error HTTP {r.status_code}", retryable=True)
        if r.status_code != 200:
            raise EmbeddingError(f"provider rejected the request: HTTP {r.status_code}")   # 4xx: do not retry
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        vectors = [d["embedding"] for d in data]
        check_dimensions(vectors, self.dimension, len(texts))
        return vectors


def get_provider(name: str | None = None) -> EmbeddingProvider:
    name = (name or settings.EMBEDDING_PROVIDER).lower()
    if name == "local":
        return LocalSentenceTransformerProvider()
    if name == "openai":
        return OpenAIProvider()
    if name == "test":
        if settings.APP_ENV.lower() == "production":
            raise EmbeddingError("the 'test' embedding provider is not allowed in production")
        return DeterministicTestProvider()
    raise EmbeddingError(f"unknown EMBEDDING_PROVIDER '{name}'")
