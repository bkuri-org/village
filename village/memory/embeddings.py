"""Embedding cache backed by Ollama + numpy cosine similarity.

Persists embeddings as a JSON file alongside the wiki. Falls back gracefully
to keyword search when Ollama is unavailable. No heavy dependencies — just
numpy for vector math and httpx (already in the project) for Ollama calls.

Storage layout:
    <store_path>/
    └── embeddings.json   # {entry_id: [float, ...]}
"""

import json
import logging
from pathlib import Path

import httpx
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
_EMBEDDING_TIMEOUT = 30.0


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between vector a (1xD) and matrix b (NxD).

    Returns a 1D array of N similarity scores.
    """
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norms = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return b_norms @ a_norm


class EmbeddingCache:
    """Manages embedding vectors for wiki entries.

    Embeddings are computed via Ollama's /api/embed endpoint and cached
    in a JSON file. On query, cosine similarity ranks entries by semantic
    relevance.
    """

    def __init__(
        self,
        cache_path: Path,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        self.cache_path = cache_path
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self._cache: dict[str, list[float]] = {}
        self._loaded = False

    def _load(self) -> None:
        """Lazy-load embeddings from disk."""
        if self._loaded:
            return
        self._loaded = True
        if not self.cache_path.exists():
            return
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._cache = {k: v for k, v in data.items() if isinstance(v, list)}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load embedding cache %s: %s", self.cache_path, exc)

    def _save(self) -> None:
        """Persist embeddings to disk."""
        try:
            self.cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to save embedding cache %s: %s", self.cache_path, exc)

    @property
    def available(self) -> bool:
        """Check if Ollama embedding endpoint is reachable."""
        try:
            resp = httpx.get(
                f"{self.ollama_url}/api/tags",
                timeout=_EMBEDDING_TIMEOUT,
            )
            return resp.status_code == 200
        except (httpx.RequestError, httpx.HTTPStatusError):
            return False

    def embed_text(self, text: str) -> list[float] | None:
        """Compute embedding for a single text via Ollama.

        Returns None if Ollama is unavailable.
        """
        try:
            resp = httpx.post(
                f"{self.ollama_url}/api/embed",
                json={"model": self.model, "input": text},
                timeout=_EMBEDDING_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            # Ollama returns {"embeddings": [[...]]}
            embeddings = data.get("embeddings", [])
            if embeddings and isinstance(embeddings[0], list):
                return embeddings[0]
            return None
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.warning("Ollama embed request failed: %s", exc)
            return None

    def get(self, entry_id: str) -> list[float] | None:
        """Retrieve cached embedding for an entry."""
        self._load()
        return self._cache.get(entry_id)

    def put(self, entry_id: str, embedding: list[float]) -> None:
        """Store embedding for an entry and persist."""
        self._load()
        self._cache[entry_id] = embedding
        self._save()

    def remove(self, entry_id: str) -> None:
        """Remove embedding for a deleted entry."""
        self._load()
        self._cache.pop(entry_id, None)
        self._save()

    def put_text(self, entry_id: str, text: str) -> bool:
        """Compute and cache embedding for text. Returns True on success."""
        embedding = self.embed_text(text)
        if embedding is not None:
            self.put(entry_id, embedding)
            return True
        return False

    def find(
        self,
        query: str,
        entry_ids: list[str],
        k: int = 5,
    ) -> list[tuple[str, float]]:
        """Find top-k entries by cosine similarity to query.

        Args:
            query: The search text.
            entry_ids: Candidate entry IDs to search among.
            k: Number of results to return.

        Returns:
            List of (entry_id, similarity_score) tuples, sorted descending.
        """
        self._load()

        query_embedding = self.embed_text(query)
        if query_embedding is None:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)

        # Collect vectors for candidates that have cached embeddings
        candidate_ids: list[str] = []
        vectors: list[np.ndarray] = []
        for eid in entry_ids:
            cached = self._cache.get(eid)
            if cached is not None:
                candidate_ids.append(eid)
                vectors.append(np.array(cached, dtype=np.float32))

        if not vectors:
            return []

        matrix = np.stack(vectors)  # (N, D)
        similarities = _cosine_similarity(query_vec, matrix)  # (N,)

        # Sort by similarity descending
        indexed = sorted(
            zip(candidate_ids, similarities.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        return indexed[:k]

    def rebuild(self, entries: dict[str, str]) -> int:
        """Rebuild embedding cache from scratch for all entries.

        Args:
            entries: Mapping of entry_id -> text content.

        Returns:
            Number of entries successfully embedded.
        """
        self._cache.clear()
        count = 0
        for entry_id, text in entries.items():
            if self.put_text(entry_id, text):
                count += 1
        self._save()
        logger.info("Rebuilt embedding cache: %d/%d entries embedded", count, len(entries))
        return count

    def needs_embedding(self, entry_ids: set[str]) -> list[str]:
        """Return entry IDs that don't have cached embeddings yet."""
        self._load()
        return [eid for eid in entry_ids if eid not in self._cache]
