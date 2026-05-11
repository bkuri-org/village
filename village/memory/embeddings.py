"""Embedding cache backed by Ollama + numpy cosine similarity.

Provides semantic search for the Village wiki by computing text embeddings
via Ollama's ``/api/embed`` endpoint and ranking candidates by cosine
similarity.  No heavy dependencies — just numpy for vector math and httpx
(already in the project) for Ollama calls.

**Storage layout** (inside the wiki ``pages/`` directory):

    pages/
    └── embeddings.json   # {entry_id: {"v": [float...], "h": "sha256_prefix"}}

**Content fingerprinting** — each cached entry stores a SHA-256 prefix
of the original text.  On :py:meth:`EmbeddingCache.sync`, entries whose
hash has changed are re-embedded, and orphaned entries (deleted from the
wiki) are pruned.  Legacy caches without hashes are auto-migrated on load.

**Public API**:

- :py:meth:`EmbeddingCache.put_text` — embed text and cache with fingerprint
- :py:meth:`EmbeddingCache.find` — semantic search with optional similarity threshold
- :py:meth:`EmbeddingCache.sync` — incremental update (new + stale + prune)
- :py:meth:`EmbeddingCache.rebuild` — full cache rebuild from scratch
- :py:meth:`EmbeddingCache.available` — Ollama health check
- :py:meth:`EmbeddingCache.remove` — delete a cached embedding
- :py:meth:`EmbeddingCache.stale` / :py:meth:`EmbeddingCache.missing` — introspection
"""

import hashlib
import json
import logging
from pathlib import Path

import httpx
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
_EMBEDDING_TIMEOUT = 30.0


def _hash_text(text: str) -> str:
    """Compute a stable SHA-256 fingerprint for content staleness detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between vector a (1xD) and matrix b (NxD).

    Returns a 1D array of N similarity scores.
    """
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norms = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return b_norms @ a_norm


class EmbeddingCache:
    """Manages embedding vectors for wiki entries with content fingerprinting.

    Embeddings are computed via Ollama's ``/api/embed`` endpoint and cached
    in a JSON file.  Each entry stores both the vector and a SHA-256 fingerprint
    of the source text, enabling incremental sync to detect stale embeddings
    when content changes.

    Usage::

        cache = EmbeddingCache(
            cache_path=wiki_path / "pages" / "embeddings.json",
            ollama_url="http://llm.lan:11434",
            model="nomic-embed-text",
        )

        # Embed a new entry
        cache.put_text("entry-001", "Some wiki content")

        # Semantic search
        results = cache.find("search query", entry_ids=["entry-001", "entry-002"], k=5, min_similarity=0.3)

        # Incremental sync (re-embed changed, embed new, prune deleted)
        cache.sync({"entry-001": "updated content", "entry-003": "new content"})
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
        # Internal format: {entry_id: {"v": [float...], "h": str}}
        # Legacy format (pre-fingerprint): {entry_id: [float...]}
        self._cache: dict[str, dict[str, object]] = {}
        self._loaded = False

    def _load(self) -> None:
        """Lazy-load embeddings from disk.

        Automatically migrates legacy format {id: [float...]} to
        fingerprinted format {id: {"v": [float...], "h": str}}.
        """
        if self._loaded:
            return
        self._loaded = True
        if not self.cache_path.exists():
            return
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            for k, v in data.items():
                if isinstance(v, dict) and "v" in v:
                    # Already in fingerprinted format
                    self._cache[k] = v
                elif isinstance(v, list):
                    # Legacy format: wrap without fingerprint (stale until synced)
                    self._cache[k] = {"v": v, "h": ""}
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
        """Retrieve cached embedding vector for an entry."""
        self._load()
        entry = self._cache.get(entry_id)
        if entry is None:
            return None
        vec = entry["v"]
        return vec if isinstance(vec, list) else None

    def get_hash(self, entry_id: str) -> str:
        """Retrieve content fingerprint for an entry. Empty string if not fingerprinted."""
        self._load()
        entry = self._cache.get(entry_id)
        if entry is None:
            return ""
        h = entry.get("h", "")
        return h if isinstance(h, str) else ""

    def put(self, entry_id: str, embedding: list[float], content_hash: str = "") -> None:
        """Store embedding for an entry and persist.

        Args:
            entry_id: Entry identifier.
            embedding: Embedding vector.
            content_hash: Optional content fingerprint for staleness detection.
        """
        self._load()
        self._cache[entry_id] = {"v": embedding, "h": content_hash}
        self._save()

    def remove(self, entry_id: str) -> None:
        """Remove embedding for a deleted entry."""
        self._load()
        self._cache.pop(entry_id, None)
        self._save()

    def put_text(self, entry_id: str, text: str) -> bool:
        """Compute and cache embedding for text. Returns True on success.

        Stores a content fingerprint (SHA-256 of text) for staleness detection.
        """
        embedding = self.embed_text(text)
        if embedding is not None:
            content_hash = _hash_text(text)
            self.put(entry_id, embedding, content_hash=content_hash)
            return True
        return False

    def find(
        self,
        query: str,
        entry_ids: list[str],
        k: int = 5,
        min_similarity: float = 0.0,
    ) -> list[tuple[str, float]]:
        """Find top-k entries by cosine similarity to query.

        Args:
            query: The search text.
            entry_ids: Candidate entry IDs to search among.
            k: Number of results to return.
            min_similarity: Minimum cosine similarity score (0.0–1.0).
                Results below this threshold are filtered out.

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
            cached_vec = self.get(eid)
            if cached_vec is not None:
                candidate_ids.append(eid)
                vectors.append(np.array(cached_vec, dtype=np.float32))

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
        return [(eid, score) for eid, score in indexed if score >= min_similarity][:k]

    def rebuild(self, entries: dict[str, str]) -> int:
        """Rebuild embedding cache from scratch for all entries.

        Stores content fingerprints so subsequent sync calls can detect
        changes efficiently.

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

    def stale(self, entries: dict[str, str]) -> list[str]:
        """Return entry IDs whose content has changed since embedding.

        Compares current text hash against stored fingerprint. Entries
        without a fingerprint (legacy or migrated) are considered stale.

        Args:
            entries: Mapping of entry_id -> text content.

        Returns:
            List of entry IDs that need re-embedding.
        """
        self._load()
        stale_ids: list[str] = []
        for entry_id, text in entries.items():
            current_hash = _hash_text(text)
            cached_hash = self.get_hash(entry_id)
            if cached_hash != current_hash:
                stale_ids.append(entry_id)
        return stale_ids

    def missing(self, entries: dict[str, str]) -> list[str]:
        """Return entry IDs that have no embedding at all.

        Args:
            entries: Mapping of entry_id -> text content.

        Returns:
            List of entry IDs without cached embeddings.
        """
        self._load()
        return [eid for eid in entries if eid not in self._cache]

    def sync(self, entries: dict[str, str]) -> int:
        """Sync embedding cache with current entries.

        Embeds missing entries and re-embeds stale ones (content changed).
        Removes embeddings for entries that no longer exist.

        Args:
            entries: Mapping of entry_id -> text content.

        Returns:
            Number of entries embedded or re-embedded.
        """
        self._load()

        # Remove embeddings for deleted entries
        current_ids = set(entries.keys())
        orphaned = set(self._cache.keys()) - current_ids
        for eid in orphaned:
            self._cache.pop(eid, None)
        if orphaned:
            logger.info("Removed %d orphaned embeddings", len(orphaned))

        # Find stale and missing entries
        stale_ids = set(self.stale(entries))
        missing_ids = set(self.missing(entries))
        to_embed = stale_ids | missing_ids

        if not to_embed:
            logger.debug("All embeddings up to date")
            return 0

        count = 0
        for eid in to_embed:
            text = entries[eid]
            if self.put_text(eid, text):
                count += 1
            else:
                logger.debug("Failed to sync embedding for %s", eid)

        logger.info("Synced embeddings: %d/%d updated", count, len(to_embed))
        return count

    def needs_embedding(self, entry_ids: set[str]) -> list[str]:
        """Return entry IDs that don't have cached embeddings yet."""
        self._load()
        return [eid for eid in entry_ids if eid not in self._cache]
